"""Settlement simplification (Section 9).

Greedy largest-creditor / largest-debtor matching. Pure and deterministic: the same
set of balances always yields the same plan, regardless of the order they arrive in,
because every comparison falls back to ascending user_id.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from app.services.balance_service import UserBalance
from app.services.split_service import ZERO, quantize_money


@dataclass(frozen=True)
class SettlementSuggestion:
    from_user_id: int
    to_user_id: int
    amount: Decimal


def suggest_settlements(balances: Sequence[UserBalance]) -> list[SettlementSuggestion]:
    """Minimise the number of transfers that zero out every balance.

    Greedy matching is not provably optimal for the general problem (it is NP-hard),
    but it is O(n log n), never produces more than n-1 transfers, and is stable --
    which matters more here than shaving off a hypothetical extra payment.
    """
    debtors: list[list] = []  # [user_id, amount_owed]
    creditors: list[list] = []  # [user_id, amount_due]

    for entry in balances:
        amount = quantize_money(entry.balance)
        if amount < ZERO:
            debtors.append([entry.user_id, -amount])
        elif amount > ZERO:
            creditors.append([entry.user_id, amount])

    # Largest first, ascending user_id as the tiebreaker -> deterministic output.
    debtors.sort(key=lambda d: (-d[1], d[0]))
    creditors.sort(key=lambda c: (-c[1], c[0]))

    suggestions: list[SettlementSuggestion] = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        debtor, owed = debtors[i]
        creditor, due = creditors[j]
        transfer = min(owed, due)

        if transfer > ZERO:
            suggestions.append(
                SettlementSuggestion(
                    from_user_id=debtor, to_user_id=creditor, amount=quantize_money(transfer)
                )
            )

        debtors[i][1] = owed - transfer
        creditors[j][1] = due - transfer
        if debtors[i][1] == ZERO:
            i += 1
        if creditors[j][1] == ZERO:
            j += 1

    return suggestions


def summarise_for_user(
    user_id: int, suggestions: Sequence[SettlementSuggestion]
) -> tuple[Decimal, Decimal]:
    """(you owe, you are owed) across the suggested plan -- the numbers the dashboard
    puts front and centre so 'how much do I owe, and who do I pay?' is one glance."""
    owe = sum((s.amount for s in suggestions if s.from_user_id == user_id), ZERO)
    owed = sum((s.amount for s in suggestions if s.to_user_id == user_id), ZERO)
    return quantize_money(owe), quantize_money(owed)
