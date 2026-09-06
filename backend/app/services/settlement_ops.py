"""Settlement writes.

Kept separate from settlement_service.py on purpose: Section 9 designates that module
as the pure simplification engine, and mixing DB access into it would make the
greedy matcher awkward to unit-test.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import GroupContext
from app.core.errors import GroupAccessDenied, PermissionDenied, ValidationError
from app.models import Settlement, User
from app.models.enums import AuditAction, MemberRole
from app.repositories import audit_repo, group_repo, settlement_repo
from app.schemas.balance import SettlementCreate
from app.services.split_service import quantize_money


async def create_settlement(
    db: AsyncSession, ctx: GroupContext, payload: SettlementCreate
) -> Settlement:
    ctx.require_write()
    ctx.require_active_group()

    if payload.from_user_id == payload.to_user_id:
        raise ValidationError("A settlement needs two different people.", "SAME_PARTY")

    member_rows = await group_repo.list_members(db, ctx.group_id)
    known = {m.user_id for m, _ in member_rows}
    for user_id in (payload.from_user_id, payload.to_user_id):
        if user_id not in known:
            raise ValidationError(
                "Both parties must belong to this group.", "PARTY_NOT_MEMBER"
            )

    # A member records a payment they were part of; an admin can record any.
    if not ctx.is_admin and ctx.user.id not in (payload.from_user_id, payload.to_user_id):
        raise PermissionDenied(
            "You can only record settlements you are part of.", "NOT_SETTLEMENT_PARTY"
        )

    settlement = await settlement_repo.create(
        db,
        group_id=ctx.group_id,
        from_user_id=payload.from_user_id,
        to_user_id=payload.to_user_id,
        amount=quantize_money(payload.amount),
        settlement_date=payload.settlement_date,
        notes=payload.notes,
        created_by=ctx.user.id,
    )
    await audit_repo.record(
        db,
        group_id=ctx.group_id,
        user_id=ctx.user.id,
        entity_type="settlement",
        entity_id=settlement.id,
        action=AuditAction.CREATE.value,
        new_value={
            "from_user_id": settlement.from_user_id,
            "to_user_id": settlement.to_user_id,
            "amount": str(settlement.amount),
            "settlement_date": settlement.settlement_date.isoformat(),
        },
    )
    await db.commit()
    await db.refresh(settlement)
    return settlement


async def reverse_settlement(db: AsyncSession, user: User, settlement_id: int) -> Settlement:
    settlement = await settlement_repo.get(db, settlement_id)
    if settlement is None:
        raise GroupAccessDenied()

    membership = await group_repo.get_membership(
        db, group_id=settlement.group_id, user_id=user.id, active_only=True
    )
    if membership is None:
        raise GroupAccessDenied()

    # Either party or an admin (Section 5).
    is_party = user.id in (settlement.from_user_id, settlement.to_user_id)
    if not is_party and membership.role != MemberRole.ADMIN.value:
        raise PermissionDenied(
            "Only the people involved or an admin can reverse this settlement.",
            "NOT_SETTLEMENT_PARTY",
        )
    if membership.role == MemberRole.VIEWER.value:
        raise PermissionDenied("Viewers have read-only access.", "READ_ONLY_ROLE")
    if settlement.is_reversed:
        raise ValidationError("This settlement is already reversed.", "ALREADY_REVERSED")

    settlement.is_reversed = True
    settlement.reversed_by = user.id
    settlement.reversed_at = datetime.now(timezone.utc)

    await audit_repo.record(
        db,
        group_id=settlement.group_id,
        user_id=user.id,
        entity_type="settlement",
        entity_id=settlement.id,
        action=AuditAction.REVERSE.value,
        old_value={"amount": str(settlement.amount), "is_reversed": False},
        new_value={"is_reversed": True},
    )
    await db.commit()
    await db.refresh(settlement)
    return settlement
