from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Settlement


async def get(db: AsyncSession, settlement_id: int) -> Settlement | None:
    return await db.get(Settlement, settlement_id)


async def list_for_group(
    db: AsyncSession,
    group_id: int,
    *,
    limit: int = 50,
    cursor_id: int | None = None,
    include_reversed: bool = True,
) -> list[Settlement]:
    stmt = (
        select(Settlement)
        .where(Settlement.group_id == group_id)
        .order_by(Settlement.settlement_date.desc(), Settlement.id.desc())
        .limit(limit)
    )
    if not include_reversed:
        stmt = stmt.where(Settlement.is_reversed.is_(False))
    if cursor_id is not None:
        anchor = await db.get(Settlement, cursor_id)
        if anchor is not None:
            stmt = stmt.where(
                (Settlement.settlement_date < anchor.settlement_date)
                | (
                    (Settlement.settlement_date == anchor.settlement_date)
                    & (Settlement.id < anchor.id)
                )
            )
    result = await db.execute(stmt)
    return list(result.scalars())


async def list_active_for_group(db: AsyncSession, group_id: int) -> list[Settlement]:
    result = await db.execute(
        select(Settlement)
        .where(Settlement.group_id == group_id, Settlement.is_reversed.is_(False))
        .order_by(Settlement.id)
    )
    return list(result.scalars())


async def create(
    db: AsyncSession,
    *,
    group_id: int,
    from_user_id: int,
    to_user_id: int,
    amount: Decimal,
    settlement_date: date,
    notes: str | None,
    created_by: int,
) -> Settlement:
    settlement = Settlement(
        group_id=group_id,
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        amount=amount,
        settlement_date=settlement_date,
        notes=notes,
        created_by=created_by,
    )
    db.add(settlement)
    await db.flush()
    return settlement
