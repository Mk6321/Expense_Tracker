"""Loads a group's financial rows and hands them to the pure engines.

This is the only place that bridges the database and the calculation code, which
keeps balance_service/settlement_service testable with plain objects.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import expense_repo, group_repo, settlement_repo
from app.services.balance_service import (
    ExpenseView,
    GroupLedger,
    SettlementView,
    UserBalance,
    compute_group_ledger,
)
from app.services.split_service import ZERO


async def load_views(
    db: AsyncSession, group_id: int
) -> tuple[list[int], list[ExpenseView], list[SettlementView]]:
    member_ids = await group_repo.active_member_ids(db, group_id)
    expenses = await expense_repo.list_active_for_group(db, group_id)
    settlements = await settlement_repo.list_active_for_group(db, group_id)

    expense_views = [
        ExpenseView(
            id=e.id,
            paid_by=e.paid_by,
            amount=Decimal(e.amount),
            splits=tuple((s.user_id, Decimal(s.amount)) for s in e.splits),
        )
        for e in expenses
    ]
    settlement_views = [
        SettlementView(
            id=s.id,
            from_user_id=s.from_user_id,
            to_user_id=s.to_user_id,
            amount=Decimal(s.amount),
        )
        for s in settlements
    ]
    return member_ids, expense_views, settlement_views


async def get_ledger(db: AsyncSession, group_id: int) -> GroupLedger:
    member_ids, expenses, settlements = await load_views(db, group_id)
    return compute_group_ledger(member_ids, expenses, settlements)


async def get_balances(db: AsyncSession, group_id: int) -> list[UserBalance]:
    return (await get_ledger(db, group_id)).balances


async def get_user_balance(db: AsyncSession, group_id: int, user_id: int) -> Decimal:
    for entry in await get_balances(db, group_id):
        if entry.user_id == user_id:
            return entry.balance
    return ZERO
