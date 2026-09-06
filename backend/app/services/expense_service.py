from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import GroupContext
from app.core.errors import (
    GroupAccessDenied,
    NotFoundError,
    OptimisticLockError,
    PermissionDenied,
    ValidationError,
)
from app.models import Expense, User
from app.models.enums import AuditAction, MemberRole, MemberStatus
from app.repositories import audit_repo, category_repo, expense_repo, group_repo
from app.schemas.expense import ExpenseCreate, ExpenseUpdate
from app.services.split_service import build_splits, quantize_money


async def _validate_people(db: AsyncSession, ctx: GroupContext, payload) -> None:
    """Payer and every participant must belong to this group.

    Removed members are allowed as participants so a historical expense can still be
    corrected, but someone who was never in the group is rejected outright -- without
    this an attacker could quietly attach another user's id to their splits.
    """
    member_rows = await group_repo.list_members(db, ctx.group_id)
    known = {m.user_id for m, _ in member_rows}
    active = {m.user_id for m, _ in member_rows if m.status == MemberStatus.ACTIVE.value}

    if payload.paid_by not in known:
        raise ValidationError("The payer is not a member of this group.", "PAYER_NOT_MEMBER")
    unknown = [p.user_id for p in payload.participants if p.user_id not in known]
    if unknown:
        raise ValidationError(
            f"User(s) {unknown} are not members of this group.", "PARTICIPANT_NOT_MEMBER"
        )
    if payload.paid_by not in active and payload.paid_by != ctx.user.id:
        raise ValidationError(
            "That member has been removed from the group.", "PAYER_NOT_ACTIVE"
        )


async def _validate_category(db: AsyncSession, ctx: GroupContext, category_id: int | None):
    if category_id is None:
        return
    category = await category_repo.get(db, category_id)
    if category is None or (category.group_id is not None and category.group_id != ctx.group_id):
        raise ValidationError("Unknown category.", "CATEGORY_NOT_FOUND")


def _snapshot(expense: Expense) -> dict:
    return {
        "description": expense.description,
        "amount": str(expense.amount),
        "paid_by": expense.paid_by,
        "expense_date": expense.expense_date.isoformat(),
        "split_type": expense.split_type,
        "category_id": expense.category_id,
        "version": expense.version,
        "splits": [{"user_id": s.user_id, "amount": str(s.amount)} for s in expense.splits],
    }


async def create_expense(
    db: AsyncSession, ctx: GroupContext, payload: ExpenseCreate
) -> Expense:
    ctx.require_write()
    ctx.require_active_group()
    await _validate_people(db, ctx, payload)
    await _validate_category(db, ctx, payload.category_id)

    total = quantize_money(payload.amount)
    lines = build_splits(
        payload.split_type.value,
        total,
        [p.model_dump() for p in payload.participants],
    )

    expense = await expense_repo.create(
        db,
        group_id=ctx.group_id,
        description=payload.description.strip(),
        amount=total,
        currency=ctx.group.currency,
        paid_by=payload.paid_by,
        category_id=payload.category_id,
        expense_date=payload.expense_date,
        split_type=payload.split_type.value,
        notes=payload.notes,
        created_by=ctx.user.id,
    )
    await expense_repo.replace_splits(db, expense, lines)
    await db.refresh(expense)

    await audit_repo.record(
        db,
        group_id=ctx.group_id,
        user_id=ctx.user.id,
        entity_type="expense",
        entity_id=expense.id,
        action=AuditAction.CREATE.value,
        new_value=_snapshot(expense),
    )
    # Expense, splits and audit entry all land in one transaction (Section 4).
    await db.commit()
    await db.refresh(expense)
    return expense


async def get_expense(db: AsyncSession, user: User, expense_id: int) -> tuple[Expense, str]:
    """Fetches an expense by its own id, re-checking group membership -- the route
    has no group_id in the path, so the usual dependency cannot cover it."""
    expense = await expense_repo.get(db, expense_id)
    if expense is None:
        raise GroupAccessDenied()

    membership = await group_repo.get_membership(
        db, group_id=expense.group_id, user_id=user.id, active_only=True
    )
    if membership is None:
        raise GroupAccessDenied()
    return expense, membership.role


def _require_edit_rights(expense: Expense, user: User, role: str) -> None:
    if expense.created_by != user.id and role != MemberRole.ADMIN.value:
        raise PermissionDenied(
            "You can only change expenses you created.", "NOT_EXPENSE_OWNER"
        )
    if role == MemberRole.VIEWER.value:
        raise PermissionDenied("Viewers have read-only access.", "READ_ONLY_ROLE")


async def update_expense(
    db: AsyncSession, user: User, expense_id: int, payload: ExpenseUpdate
) -> Expense:
    expense, role = await get_expense(db, user, expense_id)
    _require_edit_rights(expense, user, role)

    if expense.is_reversed:
        raise ValidationError("This expense has been reversed.", "EXPENSE_REVERSED")
    if expense.version != payload.version:
        raise OptimisticLockError()

    ctx = await _context_for(db, user, expense)
    await _validate_people(db, ctx, payload)
    await _validate_category(db, ctx, payload.category_id)

    old = _snapshot(expense)
    total = quantize_money(payload.amount)
    lines = build_splits(
        payload.split_type.value, total, [p.model_dump() for p in payload.participants]
    )

    expense.description = payload.description.strip()
    expense.amount = total
    expense.paid_by = payload.paid_by
    expense.category_id = payload.category_id
    expense.expense_date = payload.expense_date
    expense.split_type = payload.split_type.value
    expense.notes = payload.notes
    expense.version += 1
    await expense_repo.replace_splits(db, expense, lines)
    await db.refresh(expense)

    await audit_repo.record(
        db,
        group_id=expense.group_id,
        user_id=user.id,
        entity_type="expense",
        entity_id=expense.id,
        action=AuditAction.UPDATE.value,
        old_value=old,
        new_value=_snapshot(expense),
    )
    await db.commit()
    await db.refresh(expense)
    return expense


async def reverse_expense(db: AsyncSession, user: User, expense_id: int) -> Expense:
    """Soft reversal. The row and its splits stay put; balances just stop counting
    them, so the audit trail survives (Section 4)."""
    expense, role = await get_expense(db, user, expense_id)
    _require_edit_rights(expense, user, role)

    if expense.is_reversed:
        raise ValidationError("This expense is already reversed.", "ALREADY_REVERSED")

    old = _snapshot(expense)
    expense.is_reversed = True
    expense.reversed_by = user.id
    expense.reversed_at = datetime.now(timezone.utc)
    expense.version += 1

    await audit_repo.record(
        db,
        group_id=expense.group_id,
        user_id=user.id,
        entity_type="expense",
        entity_id=expense.id,
        action=AuditAction.REVERSE.value,
        old_value=old,
        new_value={"is_reversed": True},
    )
    await db.commit()
    await db.refresh(expense)
    return expense


async def _context_for(db: AsyncSession, user: User, expense: Expense) -> GroupContext:
    group = await group_repo.get(db, expense.group_id)
    membership = await group_repo.get_membership(
        db, group_id=expense.group_id, user_id=user.id, active_only=True
    )
    if group is None or membership is None:
        raise GroupAccessDenied()
    return GroupContext(group=group, membership=membership, user=user)


def my_share(expense: Expense, user_id: int) -> Decimal:
    return sum(
        (Decimal(s.amount) for s in expense.splits if s.user_id == user_id),
        Decimal("0.00"),
    )
