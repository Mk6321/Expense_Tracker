"""Balance and settlement engine unit tests -- the Section 13 critical scenarios."""

from __future__ import annotations

from decimal import Decimal

from app.services.balance_service import (
    ExpenseView,
    SettlementView,
    compute_balances,
    compute_pairwise_ledger,
)
from app.services.settlement_service import suggest_settlements
from app.services.split_service import split_equal

ZERO = Decimal("0.00")


def expense(id_: int, paid_by: int, amount: str, participants: list[int]) -> ExpenseView:
    lines = split_equal(Decimal(amount), participants)
    return ExpenseView(
        id=id_,
        paid_by=paid_by,
        amount=Decimal(amount),
        splits=tuple((line.user_id, line.amount) for line in lines),
    )


def by_id(balances):
    return {b.user_id: b.balance for b in balances}


def test_scenario_1_one_payer_six_participants():
    members = [1, 2, 3, 4, 5, 6]
    balances = compute_balances(members, [expense(1, 1, "600.00", members)], [])
    result = by_id(balances)

    assert result[1] == Decimal("500.00")  # paid 600, owes 100 -> +5x share
    for uid in members[1:]:
        assert result[uid] == Decimal("-100.00")
    assert sum(result.values()) == ZERO


def test_scenario_2_two_participants():
    balances = compute_balances([1, 2], [expense(1, 1, "50.00", [1, 2])], [])
    assert by_id(balances) == {1: Decimal("25.00"), 2: Decimal("-25.00")}


def test_scenario_3_unequal_exact_split():
    view = ExpenseView(
        id=1,
        paid_by=1,
        amount=Decimal("100.00"),
        splits=((1, Decimal("20.00")), (2, Decimal("35.00")), (3, Decimal("45.00"))),
    )
    result = by_id(compute_balances([1, 2, 3], [view], []))
    assert result == {1: Decimal("80.00"), 2: Decimal("-35.00"), 3: Decimal("-45.00")}
    assert sum(result.values()) == ZERO


def test_scenario_4_aggregates_across_many_expenses():
    members = [1, 2, 3]
    expenses = [
        expense(1, 1, "300.00", members),
        expense(2, 2, "60.00", members),
        expense(3, 3, "90.00", [1, 3]),
        expense(4, 1, "15.00", [2]),
    ]
    result = by_id(compute_balances(members, expenses, []))
    # Every rupee that goes in comes back out.
    assert sum(result.values()) == ZERO
    assert result[1] == Decimal("300.00") - Decimal("100.00") - Decimal("20.00") - Decimal(
        "45.00"
    ) + Decimal("15.00")


def test_scenario_5_settlement_reduces_the_right_balance():
    members = [1, 2, 3]
    expenses = [expense(1, 1, "300.00", members)]
    settlements = [SettlementView(id=1, from_user_id=2, to_user_id=1, amount=Decimal("100.00"))]

    result = by_id(compute_balances(members, expenses, settlements))
    assert result[2] == ZERO
    assert result[1] == Decimal("100.00")
    assert result[3] == Decimal("-100.00")
    assert sum(result.values()) == ZERO


def test_scenario_6_multiple_settlements_net_out():
    members = [1, 2, 3]
    expenses = [expense(1, 1, "300.00", members)]
    settlements = [
        SettlementView(id=1, from_user_id=2, to_user_id=1, amount=Decimal("100.00")),
        SettlementView(id=2, from_user_id=3, to_user_id=1, amount=Decimal("100.00")),
    ]
    result = by_id(compute_balances(members, expenses, settlements))
    assert all(value == ZERO for value in result.values())


def test_scenario_7_reversed_rows_are_simply_excluded():
    """Reversal is modelled as the caller not passing the row -- there is no code
    path that deletes it, so the audit trail survives."""
    members = [1, 2, 3]
    kept = expense(1, 1, "300.00", members)
    reversed_row = expense(2, 2, "90.00", members)

    with_both = by_id(compute_balances(members, [kept, reversed_row], []))
    after_reversal = by_id(compute_balances(members, [kept], []))

    assert with_both != after_reversal
    assert after_reversal == {
        1: Decimal("200.00"),
        2: Decimal("-100.00"),
        3: Decimal("-100.00"),
    }


def test_scenario_8_hundred_three_ways_balances_to_the_cent():
    members = [1, 2, 3]
    result = by_id(compute_balances(members, [expense(1, 1, "100.00", members)], []))
    assert sum(result.values()) == ZERO
    assert result[1] == Decimal("66.66")  # paid 100, own share 33.34
    assert result[2] == Decimal("-33.33")
    assert result[3] == Decimal("-33.33")


def test_removed_member_with_history_still_appears():
    """User 9 is not in the active member list but has a historical split."""
    view = ExpenseView(
        id=1,
        paid_by=1,
        amount=Decimal("100.00"),
        splits=((1, Decimal("50.00")), (9, Decimal("50.00"))),
    )
    result = by_id(compute_balances([1], [view], []))
    assert result[9] == Decimal("-50.00")


class TestPairwiseLedger:
    def test_direct_debts_from_shared_expenses(self):
        debts = compute_pairwise_ledger([expense(1, 1, "300.00", [1, 2, 3])], [])
        assert [(d.from_user_id, d.to_user_id, d.amount) for d in debts] == [
            (2, 1, Decimal("100.00")),
            (3, 1, Decimal("100.00")),
        ]

    def test_opposite_debts_cancel(self):
        debts = compute_pairwise_ledger(
            [expense(1, 1, "100.00", [1, 2]), expense(2, 2, "40.00", [1, 2])], []
        )
        assert [(d.from_user_id, d.to_user_id, d.amount) for d in debts] == [
            (2, 1, Decimal("30.00"))
        ]

    def test_settlement_clears_the_pair(self):
        debts = compute_pairwise_ledger(
            [expense(1, 1, "100.00", [1, 2])],
            [SettlementView(id=1, from_user_id=2, to_user_id=1, amount=Decimal("50.00"))],
        )
        assert debts == []


class TestSuggestions:
    def test_minimises_transfers(self):
        members = [1, 2, 3]
        balances = compute_balances(members, [expense(1, 1, "300.00", members)], [])
        suggestions = suggest_settlements(balances)
        assert len(suggestions) == 2
        assert all(s.to_user_id == 1 for s in suggestions)
        assert sum(s.amount for s in suggestions) == Decimal("200.00")

    def test_deterministic_regardless_of_input_order(self):
        members = [1, 2, 3, 4]
        expenses = [expense(1, 1, "400.00", members), expense(2, 2, "80.00", members)]
        forward = compute_balances(members, expenses, [])
        backward = compute_balances(list(reversed(members)), list(reversed(expenses)), [])

        assert suggest_settlements(forward) == suggest_settlements(backward)

    def test_settled_group_needs_no_transfers(self):
        members = [1, 2]
        expenses = [expense(1, 1, "100.00", members)]
        settlements = [
            SettlementView(id=1, from_user_id=2, to_user_id=1, amount=Decimal("50.00"))
        ]
        assert suggest_settlements(compute_balances(members, expenses, settlements)) == []

    def test_plan_fully_clears_every_balance(self):
        members = [1, 2, 3, 4, 5, 6]
        expenses = [
            expense(1, 1, "100.00", members),
            expense(2, 3, "55.00", [3, 4, 5]),
            expense(3, 6, "13.00", [1, 6]),
        ]
        balances = compute_balances(members, expenses, [])
        applied = [
            SettlementView(id=i, from_user_id=s.from_user_id, to_user_id=s.to_user_id,
                           amount=s.amount)
            for i, s in enumerate(suggest_settlements(balances), start=1)
        ]
        after = compute_balances(members, expenses, applied)
        assert all(b.balance == ZERO for b in after)
