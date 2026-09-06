from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import GroupContext
from app.core.errors import ConflictError, NotFoundError, PermissionDenied, ValidationError
from app.core.security import generate_invite_code
from app.models import Group, GroupInvite, GroupMember, User
from app.models.enums import AuditAction, MemberRole, MemberStatus
from app.repositories import audit_repo, group_repo, user_repo
from app.services import ledger_service
from app.services.split_service import ZERO


async def create_group(db: AsyncSession, *, user: User, name: str, currency: str) -> Group:
    group = await group_repo.create(db, name=name, currency=currency, created_by=user.id)
    await group_repo.add_member(
        db, group_id=group.id, user_id=user.id, role=MemberRole.ADMIN.value
    )
    await audit_repo.record(
        db,
        group_id=group.id,
        user_id=user.id,
        entity_type="group",
        entity_id=group.id,
        action=AuditAction.CREATE.value,
        new_value={"name": name, "currency": currency},
    )
    await db.commit()
    await db.refresh(group)
    return group


async def list_groups(db: AsyncSession, user: User) -> list[tuple[Group, str, int]]:
    rows = await group_repo.list_for_user(db, user.id)
    counts = await group_repo.member_counts(db, [g.id for g, _ in rows])
    return [(g, role, counts.get(g.id, 0)) for g, role in rows]


async def update_group(
    db: AsyncSession, ctx: GroupContext, *, name: str | None, currency: str | None
) -> Group:
    ctx.require_admin()
    old = {"name": ctx.group.name, "currency": ctx.group.currency}
    if name is not None:
        ctx.group.name = name.strip()
    if currency is not None:
        ctx.group.currency = currency.upper()

    await audit_repo.record(
        db,
        group_id=ctx.group_id,
        user_id=ctx.user.id,
        entity_type="group",
        entity_id=ctx.group_id,
        action=AuditAction.UPDATE.value,
        old_value=old,
        new_value={"name": ctx.group.name, "currency": ctx.group.currency},
    )
    await db.commit()
    await db.refresh(ctx.group)
    return ctx.group


async def archive_group(db: AsyncSession, ctx: GroupContext) -> Group:
    """DELETE on a group archives it -- financial history is never destroyed."""
    ctx.require_admin()
    ctx.group.is_archived = True
    await audit_repo.record(
        db,
        group_id=ctx.group_id,
        user_id=ctx.user.id,
        entity_type="group",
        entity_id=ctx.group_id,
        action=AuditAction.GROUP_ARCHIVE.value,
        new_value={"is_archived": True},
    )
    await db.commit()
    await db.refresh(ctx.group)
    return ctx.group


async def create_invite(db: AsyncSession, ctx: GroupContext) -> GroupInvite:
    ctx.require_admin()
    ctx.require_active_group()

    # Collisions are vanishingly unlikely with 32^8 codes, but the column is unique
    # so retry rather than blow up on the constraint.
    for _ in range(5):
        code = generate_invite_code()
        if await group_repo.get_invite_by_code(db, code) is None:
            break
    else:
        raise ConflictError("Could not allocate an invite code.", "INVITE_CODE_COLLISION")

    invite = await group_repo.create_invite(
        db,
        group_id=ctx.group_id,
        code=code,
        created_by=ctx.user.id,
        expire_days=settings.INVITE_CODE_EXPIRE_DAYS,
    )
    await db.commit()
    await db.refresh(invite)
    return invite


async def revoke_invite(db: AsyncSession, ctx: GroupContext, code: str) -> GroupInvite:
    ctx.require_admin()
    invite = await group_repo.get_invite_by_code(db, code.upper())
    if invite is None or invite.group_id != ctx.group_id:
        raise NotFoundError("Invite not found.", "INVITE_NOT_FOUND")
    invite.is_revoked = True
    await db.commit()
    await db.refresh(invite)
    return invite


async def join_group(db: AsyncSession, *, user: User, invite_code: str) -> Group:
    invite = await group_repo.get_invite_by_code(db, invite_code.upper())
    if invite is None:
        raise NotFoundError("That invite code is not valid.", "INVITE_INVALID")
    if invite.is_revoked:
        raise ValidationError("That invite code has been revoked.", "INVITE_REVOKED")

    expires_at = invite.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise ValidationError("That invite code has expired.", "INVITE_EXPIRED")

    group = await group_repo.get(db, invite.group_id)
    if group is None:
        raise NotFoundError("That invite code is not valid.", "INVITE_INVALID")
    if group.is_archived:
        raise ValidationError("That group has been archived.", "GROUP_ARCHIVED")

    existing = await group_repo.get_membership(
        db, group_id=group.id, user_id=user.id, active_only=False
    )
    if existing is not None:
        if existing.status == MemberStatus.ACTIVE.value:
            raise ConflictError("You are already a member of this group.", "ALREADY_MEMBER")
        # Rejoining: reactivate the original row so historical splits stay attached.
        existing.status = MemberStatus.ACTIVE.value
    else:
        await group_repo.add_member(
            db, group_id=group.id, user_id=user.id, role=MemberRole.MEMBER.value
        )

    await audit_repo.record(
        db,
        group_id=group.id,
        user_id=user.id,
        entity_type="group_member",
        entity_id=user.id,
        action=AuditAction.MEMBER_ADD.value,
        new_value={"via": "invite", "code": invite.code},
    )
    await db.commit()
    await db.refresh(group)
    return group


async def list_members(db: AsyncSession, ctx: GroupContext) -> list[tuple[GroupMember, User]]:
    return await group_repo.list_members(db, ctx.group_id)


async def change_role(
    db: AsyncSession, ctx: GroupContext, *, target_user_id: int, role: str
) -> GroupMember:
    ctx.require_admin()
    member = await group_repo.get_membership(
        db, group_id=ctx.group_id, user_id=target_user_id, active_only=True
    )
    if member is None:
        raise NotFoundError("That member is not in this group.", "MEMBER_NOT_FOUND")

    if (
        member.role == MemberRole.ADMIN.value
        and role != MemberRole.ADMIN.value
        and await group_repo.count_admins(db, ctx.group_id) <= 1
    ):
        raise ValidationError(
            "A group must keep at least one admin.", "LAST_ADMIN"
        )

    old_role = member.role
    member.role = role
    await audit_repo.record(
        db,
        group_id=ctx.group_id,
        user_id=ctx.user.id,
        entity_type="group_member",
        entity_id=target_user_id,
        action=AuditAction.ROLE_CHANGE.value,
        old_value={"role": old_role},
        new_value={"role": role},
    )
    await db.commit()
    await db.refresh(member)
    return member


async def remove_member(
    db: AsyncSession, ctx: GroupContext, *, target_user_id: int, force: bool = False
):
    """Soft-removes a member. Blocked while their balance is non-zero unless an
    admin explicitly forces it (Section 4)."""
    ctx.require_admin()

    member = await group_repo.get_membership(
        db, group_id=ctx.group_id, user_id=target_user_id, active_only=True
    )
    if member is None:
        raise NotFoundError("That member is not in this group.", "MEMBER_NOT_FOUND")

    if (
        member.role == MemberRole.ADMIN.value
        and await group_repo.count_admins(db, ctx.group_id) <= 1
    ):
        raise ValidationError("A group must keep at least one admin.", "LAST_ADMIN")

    balance = await ledger_service.get_user_balance(db, ctx.group_id, target_user_id)
    if balance != ZERO and not force:
        raise ConflictError(
            f"This member still has an outstanding balance of {balance}. "
            "Settle up first, or force-remove to keep the debt in the history.",
            "MEMBER_HAS_BALANCE",
        )

    member.status = MemberStatus.REMOVED.value
    await audit_repo.record(
        db,
        group_id=ctx.group_id,
        user_id=ctx.user.id,
        entity_type="group_member",
        entity_id=target_user_id,
        action=AuditAction.MEMBER_REMOVE.value,
        old_value={"status": MemberStatus.ACTIVE.value},
        new_value={"status": MemberStatus.REMOVED.value, "forced": force,
                   "balance_at_removal": str(balance)},
    )
    await db.commit()
    return member, balance
