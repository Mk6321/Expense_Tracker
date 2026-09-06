from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Expense, ExpenseSplit


async def get(db: AsyncSession, expense_id: int) -> Expense | None:
    result = await db.execute(
        select(Expense).options(selectinload(Expense.splits)).where(Expense.id == expense_id)
    )
    return result.scalar_one_or_none()


async def list_for_group(
    db: AsyncSession,
    group_id: int,
    *,
    limit: int = 50,
    cursor_id: int | None = None,
    include_reversed: bool = True,
    category_id: int | None = None,
    paid_by: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[Expense]:
    """Keyset pagination on (expense_date desc, id desc) -- stable under inserts,
    unlike OFFSET. `cursor_id` is the last id from the previous page."""
    stmt = (
        select(Expense)
        .options(selectinload(Expense.splits))
        .where(Expense.group_id == group_id)
        .order_by(Expense.expense_date.desc(), Expense.id.desc())
        .limit(limit)
    )
    if not include_reversed:
        stmt = stmt.where(Expense.is_reversed.is_(False))
    if category_id is not None:
        stmt = stmt.where(Expense.category_id == category_id)
    if paid_by is not None:
        stmt = stmt.where(Expense.paid_by == paid_by)
    if date_from is not None:
        stmt = stmt.where(Expense.expense_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Expense.expense_date <= date_to)
    if cursor_id is not None:
        anchor = await db.get(Expense, cursor_id)
        if anchor is not None:
            stmt = stmt.where(
                (Expense.expense_date < anchor.expense_date)
                | (
                    (Expense.expense_date == anchor.expense_date)
                    & (Expense.id < anchor.id)
                )
            )
    result = await db.execute(stmt)
    return list(result.scalars())


async def list_active_for_group(db: AsyncSession, group_id: int) -> list[Expense]:
    """Every non-reversed expense with its splits -- the input to the balance engine."""
    result = await db.execute(
        select(Expense)
        .options(selectinload(Expense.splits))
        .where(Expense.group_id == group_id, Expense.is_reversed.is_(False))
        .order_by(Expense.id)
    )
    return list(result.scalars())


async def create(
    db: AsyncSession,
    *,
    group_id: int,
    description: str,
    amount: Decimal,
    currency: str,
    paid_by: int,
    category_id: int | None,
    expense_date: date,
    split_type: str,
    notes: str | None,
    created_by: int,
) -> Expense:
    expense = Expense(
        group_id=group_id,
        description=description,
        amount=amount,
        currency=currency,
        paid_by=paid_by,
        category_id=category_id,
        expense_date=expense_date,
        split_type=split_type,
        notes=notes,
        created_by=created_by,
        version=1,
    )
    db.add(expense)
    await db.flush()
    return expense


async def replace_splits(db: AsyncSession, expense: Expense, lines) -> None:
    """Splits are rewritten wholesale on update -- there is no partial-split edit
    path, which keeps the sum-equals-total invariant trivially checkable."""
    # Deleted with an explicit statement rather than expense.splits.clear(): touching
    # the relationship on a just-flushed object triggers a lazy load, which is not
    # allowed inside async SQLAlchemy.
    await db.execute(delete(ExpenseSplit).where(ExpenseSplit.expense_id == expense.id))
    await db.flush()
    for line in lines:
        db.add(
            ExpenseSplit(
                expense_id=expense.id,
                user_id=line.user_id,
                amount=line.amount,
                percentage=line.percentage,
                shares=line.shares,
            )
        )
    await db.flush()
