from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import GroupContext
from app.repositories import category_repo, expense_repo, group_repo
from app.schemas.report import (
    CategoryReportRow,
    MemberReportRow,
    MonthlyReportRow,
    SummaryOut,
)
from app.services import ledger_service
from app.services.split_service import ZERO, quantize_money

# Groups are small (single digits of members, hundreds of expenses), so reports are
# aggregated in Python from the same rows the balance engine uses. That keeps one
# definition of "spend" instead of a second one written in SQL that can drift.


async def summary(db: AsyncSession, ctx: GroupContext) -> SummaryOut:
    expenses = await expense_repo.list_active_for_group(db, ctx.group_id)
    balances = await ledger_service.get_balances(db, ctx.group_id)
    member_ids = await group_repo.active_member_ids(db, ctx.group_id)

    total = sum((Decimal(e.amount) for e in expenses), ZERO)
    largest = max((Decimal(e.amount) for e in expenses), default=ZERO)
    dates = sorted(e.expense_date for e in expenses)
    mine = next((b for b in balances if b.user_id == ctx.user.id), None)

    return SummaryOut(
        group_id=ctx.group_id,
        currency=ctx.group.currency,
        total_spend=quantize_money(total),
        expense_count=len(expenses),
        member_count=len(member_ids),
        my_total_paid=mine.total_paid if mine else ZERO,
        my_total_share=mine.total_share if mine else ZERO,
        my_balance=mine.balance if mine else ZERO,
        average_expense=quantize_money(total / len(expenses)) if expenses else ZERO,
        largest_expense=quantize_money(largest),
        first_expense_date=dates[0] if dates else None,
        last_expense_date=dates[-1] if dates else None,
    )


async def by_category(db: AsyncSession, ctx: GroupContext) -> list[CategoryReportRow]:
    expenses = await expense_repo.list_active_for_group(db, ctx.group_id)
    categories = {c.id: c for c in await category_repo.list_for_group(db, ctx.group_id)}

    totals: dict[int | None, Decimal] = {}
    counts: dict[int | None, int] = {}
    for expense in expenses:
        key = expense.category_id
        totals[key] = totals.get(key, ZERO) + Decimal(expense.amount)
        counts[key] = counts.get(key, 0) + 1

    grand_total = sum(totals.values(), ZERO)
    rows: list[CategoryReportRow] = []
    for key, total in totals.items():
        category = categories.get(key) if key is not None else None
        share = (total / grand_total * 100) if grand_total else ZERO
        rows.append(
            CategoryReportRow(
                category_id=key,
                category_name=category.name if category else "Uncategorised",
                icon=category.icon if category else None,
                total=quantize_money(total),
                expense_count=counts[key],
                percentage=str(quantize_money(share)),
            )
        )
    return sorted(rows, key=lambda r: (-r.total, r.category_name))


async def by_member(db: AsyncSession, ctx: GroupContext) -> list[MemberReportRow]:
    balances = await ledger_service.get_balances(db, ctx.group_id)
    expenses = await expense_repo.list_active_for_group(db, ctx.group_id)
    members = {m.user_id: u for m, u in await group_repo.list_members(db, ctx.group_id)}

    paid_counts: dict[int, int] = {}
    for expense in expenses:
        paid_counts[expense.paid_by] = paid_counts.get(expense.paid_by, 0) + 1

    rows = [
        MemberReportRow(
            user_id=b.user_id,
            name=members[b.user_id].name if b.user_id in members else "Former member",
            total_paid=b.total_paid,
            total_share=b.total_share,
            balance=b.balance,
            expense_count=paid_counts.get(b.user_id, 0),
        )
        for b in balances
    ]
    return sorted(rows, key=lambda r: (-r.total_paid, r.name))


async def monthly(db: AsyncSession, ctx: GroupContext) -> list[MonthlyReportRow]:
    expenses = await expense_repo.list_active_for_group(db, ctx.group_id)

    totals: dict[str, Decimal] = {}
    counts: dict[str, int] = {}
    my_share: dict[str, Decimal] = {}

    for expense in expenses:
        month = expense.expense_date.strftime("%Y-%m")
        totals[month] = totals.get(month, ZERO) + Decimal(expense.amount)
        counts[month] = counts.get(month, 0) + 1
        mine = sum(
            (Decimal(s.amount) for s in expense.splits if s.user_id == ctx.user.id), ZERO
        )
        my_share[month] = my_share.get(month, ZERO) + mine

    return [
        MonthlyReportRow(
            month=month,
            total=quantize_money(totals[month]),
            expense_count=counts[month],
            my_share=quantize_money(my_share[month]),
        )
        for month in sorted(totals)
    ]
