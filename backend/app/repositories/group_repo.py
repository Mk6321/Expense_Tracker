from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Group, GroupInvite, GroupMember, User
from app.models.enums import MemberRole, MemberStatus


async def get(db: AsyncSession, group_id: int) -> Group | None:
    return await db.get(Group, group_id)


async def create(db: AsyncSession, *, name: str, currency: str, created_by: int) -> Group:
    group = Group(name=name, currency=currency, created_by=created_by)
    db.add(group)
    await db.flush()
    return group


async def add_member(
    db: AsyncSession, *, group_id: int, user_id: int, role: str
) -> GroupMember:
    member = GroupMember(group_id=group_id, user_id=user_id, role=role,
                         status=MemberStatus.ACTIVE.value)
    db.add(member)
    await db.flush()
    return member


async def get_membership(
    db: AsyncSession, *, group_id: int, user_id: int, active_only: bool = True
) -> GroupMember | None:
    stmt = select(GroupMember).where(
        GroupMember.group_id == group_id, GroupMember.user_id == user_id
    )
    if active_only:
        stmt = stmt.where(GroupMember.status == MemberStatus.ACTIVE.value)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_members(
    db: AsyncSession, group_id: int, *, include_removed: bool = True
) -> list[tuple[GroupMember, User]]:
    stmt = (
        select(GroupMember, User)
        .join(User, User.id == GroupMember.user_id)
        .where(GroupMember.group_id == group_id)
        .order_by(GroupMember.joined_at, GroupMember.user_id)
    )
    if not include_removed:
        stmt = stmt.where(GroupMember.status == MemberStatus.ACTIVE.value)
    result = await db.execute(stmt)
    return [(m, u) for m, u in result.all()]


async def active_member_ids(db: AsyncSession, group_id: int) -> list[int]:
    result = await db.execute(
        select(GroupMember.user_id)
        .where(
            GroupMember.group_id == group_id,
            GroupMember.status == MemberStatus.ACTIVE.value,
        )
        .order_by(GroupMember.user_id)
    )
    return list(result.scalars())


async def list_for_user(db: AsyncSession, user_id: int) -> list[tuple[Group, str]]:
    result = await db.execute(
        select(Group, GroupMember.role)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .where(
            GroupMember.user_id == user_id,
            GroupMember.status == MemberStatus.ACTIVE.value,
        )
        .order_by(Group.created_at.desc())
    )
    return [(g, role) for g, role in result.all()]


async def member_counts(db: AsyncSession, group_ids: list[int]) -> dict[int, int]:
    if not group_ids:
        return {}
    result = await db.execute(
        select(GroupMember.group_id, func.count())
        .where(
            GroupMember.group_id.in_(group_ids),
            GroupMember.status == MemberStatus.ACTIVE.value,
        )
        .group_by(GroupMember.group_id)
    )
    return {gid: count for gid, count in result.all()}


async def count_admins(db: AsyncSession, group_id: int) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(GroupMember)
        .where(
            GroupMember.group_id == group_id,
            GroupMember.role == MemberRole.ADMIN.value,
            GroupMember.status == MemberStatus.ACTIVE.value,
        )
    )
    return int(result.scalar_one())


async def create_invite(
    db: AsyncSession, *, group_id: int, code: str, created_by: int, expire_days: int
) -> GroupInvite:
    invite = GroupInvite(
        group_id=group_id,
        code=code,
        created_by=created_by,
        expires_at=datetime.now(timezone.utc) + timedelta(days=expire_days),
    )
    db.add(invite)
    await db.flush()
    return invite


async def get_invite_by_code(db: AsyncSession, code: str) -> GroupInvite | None:
    result = await db.execute(select(GroupInvite).where(GroupInvite.code == code))
    return result.scalar_one_or_none()


async def list_invites(db: AsyncSession, group_id: int) -> list[GroupInvite]:
    result = await db.execute(
        select(GroupInvite)
        .where(GroupInvite.group_id == group_id)
        .order_by(GroupInvite.created_at.desc())
    )
    return list(result.scalars())
