"""Balance engine (Section 9).

Balances are always derived live from expense splits and settlement rows. There is
no stored, hand-editable balance column anywhere in the schema, by design. The pure
functions here take plain value objects so they can be unit-tested without a DB.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable, Sequence

from app.services.split_service import ZERO, quantize_money


@dataclass(frozen=True)
class ExpenseView:
    """The only facts the balance engine needs about an expense."""

    id: int
    paid_by: int
    amount: Decimal
    splits: tuple[tuple[int, Decimal], ...]  # (user_id, share_amount)


@dataclass(frozen=True)
class SettlementView:
    id: int
    from_user_id: int
    to_user_id: int
    amount: Decimal


@dataclass
class UserBalance:
    user_id: int
    total_paid: Decimal = ZERO
    total_share: Decimal = ZERO
    settlements_paid: Decimal = ZERO
    settlements_received: Decimal = ZERO

    @property
    def balance(self) -> Decimal:
        """Positive => the group owes this user. Negative => this user owes the group."""
        return quantize_money(
            self.total_paid
            - self.total_share
            + self.settlements_paid
            - self.settlements_received
        )


@dataclass(frozen=True)
class PairwiseDebt:
    """`from_user_id` owes `to_user_id` this much."""

    from_user_id: int
    to_user_id: int
    amount: Decimal


@dataclass
class GroupLedger:
    balances: list[UserBalance] = field(default_factory=list)
    pairwise: list[PairwiseDebt] = field(default_factory=list)

    @property
    def total_outstanding(self) -> Decimal:
        return quantize_money(sum((d.amount for d in self.pairwise), ZERO))


def compute_balances(
    member_ids: Sequence[int],
    expenses: Iterable[ExpenseView],
    settlements: Iterable[SettlementView],
) -> list[UserBalance]:
    """Net balance per member. Callers pass only non-reversed rows."""
    by_id: dict[int, UserBalance] = {uid: UserBalance(user_id=uid) for uid in member_ids}

    def slot(user_id: int) -> UserBalance:
        # A removed member can still carry historical splits, so they may show up
        # here without being in the active member list.
        if user_id not in by_id:
            by_id[user_id] = UserBalance(user_id=user_id)
        return by_id[user_id]

    for expense in expenses:
        slot(expense.paid_by).total_paid += expense.amount
        for user_id, share in expense.splits:
            slot(user_id).total_share += share

    for settlement in settlements:
        slot(settlement.from_user_id).settlements_paid += settlement.amount
        slot(settlement.to_user_id).settlements_received += settlement.amount

    for balance in by_id.values():
        balance.total_paid = quantize_money(balance.total_paid)
        balance.total_share = quantize_money(balance.total_share)
        balance.settlements_paid = quantize_money(balance.settlements_paid)
        balance.settlements_received = quantize_money(balance.settlements_received)

    return sorted(by_id.values(), key=lambda b: b.user_id)


def compute_pairwise_ledger(
    expenses: Iterable[ExpenseView],
    settlements: Iterable[SettlementView],
) -> list[PairwiseDebt]:
    """Who-owes-whom derived from actual shared expenses, unsimplified (Section 9).

    Every expense creates a direct debt from each participant to whoever paid. The
    simplified plan can suggest a payment between two people who never shared an
    expense, which users find baffling -- this is the view they fall back on.
    """
    net: dict[tuple[int, int], Decimal] = {}

    def add(debtor: int, creditor: int, amount: Decimal) -> None:
        if debtor == creditor or amount == ZERO:
            return
        # Store each pair under one canonical key so A->B and B->A cancel out.
        key = (debtor, creditor) if debtor < creditor else (creditor, debtor)
        signed = amount if key == (debtor, creditor) else -amount
        net[key] = net.get(key, ZERO) + signed

    for expense in expenses:
        for user_id, share in expense.splits:
            add(user_id, expense.paid_by, share)

    for settlement in settlements:
        # Paying someone reduces what you owe them.
        add(settlement.to_user_id, settlement.from_user_id, settlement.amount)

    debts: list[PairwiseDebt] = []
    for (a, b), amount in net.items():
        amount = quantize_money(amount)
        if amount > ZERO:
            debts.append(PairwiseDebt(from_user_id=a, to_user_id=b, amount=amount))
        elif amount < ZERO:
            debts.append(PairwiseDebt(from_user_id=b, to_user_id=a, amount=-amount))

    return sorted(debts, key=lambda d: (d.from_user_id, d.to_user_id))


def compute_group_ledger(
    member_ids: Sequence[int],
    expenses: Sequence[ExpenseView],
    settlements: Sequence[SettlementView],
) -> GroupLedger:
    return GroupLedger(
        balances=compute_balances(member_ids, expenses, settlements),
        pairwise=compute_pairwise_ledger(expenses, settlements),
    )
