"""Split engine unit tests -- no DB, no HTTP (Section 8/13)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.errors import ValidationError
from app.services.split_service import (
    build_splits,
    split_equal,
    split_exact,
    split_percentage,
    split_shares,
)


def amounts(lines):
    return [line.amount for line in lines]


def total(lines):
    return sum(amounts(lines), Decimal("0.00"))


class TestEqual:
    def test_divides_evenly(self):
        lines = split_equal(Decimal("120.00"), [1, 2, 3])
        assert amounts(lines) == [Decimal("40.00")] * 3

    def test_hundred_three_ways_sums_exactly(self):
        """Section 13 scenario 8."""
        lines = split_equal(Decimal("100.00"), [1, 2, 3])
        assert total(lines) == Decimal("100.00")
        assert amounts(lines) == [Decimal("33.34"), Decimal("33.33"), Decimal("33.33")]

    def test_remainder_goes_to_lowest_user_id_not_first_in_list(self):
        """All remainders tie at 1/3, so the tiebreak is user_id -- and the answer
        must not change when the caller shuffles the list."""
        shuffled = split_equal(Decimal("100.00"), [7, 3, 5])
        by_id = {line.user_id: line.amount for line in shuffled}
        assert by_id[3] == Decimal("33.34")
        assert by_id[5] == Decimal("33.33")
        assert by_id[7] == Decimal("33.33")

    def test_six_participants(self):
        lines = split_equal(Decimal("100.00"), [1, 2, 3, 4, 5, 6])
        assert total(lines) == Decimal("100.00")
        assert sorted(amounts(lines))[0] == Decimal("16.66")

    def test_two_participants_odd_cent(self):
        """Section 13 scenario 2."""
        lines = split_equal(Decimal("0.01"), [1, 2])
        assert amounts(lines) == [Decimal("0.01"), Decimal("0.00")]
        assert total(lines) == Decimal("0.01")

    def test_single_participant_takes_everything(self):
        assert amounts(split_equal(Decimal("99.99"), [4])) == [Decimal("99.99")]

    @pytest.mark.parametrize("total_amount", ["0.03", "10.00", "100.00", "999.99", "0.05"])
    @pytest.mark.parametrize("count", [2, 3, 5, 6, 7, 11])
    def test_always_sums_to_the_total(self, total_amount, count):
        lines = split_equal(Decimal(total_amount), list(range(1, count + 1)))
        assert total(lines) == Decimal(total_amount)

    def test_rejects_zero_amount(self):
        with pytest.raises(ValidationError):
            split_equal(Decimal("0.00"), [1, 2])

    def test_rejects_duplicate_participant(self):
        with pytest.raises(ValidationError):
            split_equal(Decimal("10.00"), [1, 1])


class TestExact:
    def test_accepts_matching_sum(self):
        """Section 13 scenario 3."""
        lines = split_exact(
            Decimal("100.00"),
            [(1, Decimal("55.50")), (2, Decimal("30.25")), (3, Decimal("14.25"))],
        )
        assert total(lines) == Decimal("100.00")

    def test_rejects_mismatched_sum(self):
        with pytest.raises(ValidationError) as exc:
            split_exact(Decimal("100.00"), [(1, Decimal("50.00")), (2, Decimal("49.99"))])
        assert exc.value.error_code == "SPLIT_SUM_MISMATCH"

    def test_rejects_negative_amount(self):
        with pytest.raises(ValidationError):
            split_exact(Decimal("10.00"), [(1, Decimal("12.00")), (2, Decimal("-2.00"))])


class TestPercentage:
    def test_simple_thirds(self):
        lines = split_percentage(
            Decimal("100.00"),
            [(1, Decimal("33.34")), (2, Decimal("33.33")), (3, Decimal("33.33"))],
        )
        assert total(lines) == Decimal("100.00")

    def test_rejects_sum_not_hundred(self):
        with pytest.raises(ValidationError) as exc:
            split_percentage(Decimal("100.00"), [(1, Decimal("60")), (2, Decimal("30"))])
        assert exc.value.error_code == "PERCENTAGE_SUM_MISMATCH"

    def test_uneven_percentages_still_sum(self):
        lines = split_percentage(
            Decimal("0.10"),
            [(1, Decimal("33.333")), (2, Decimal("33.333")), (3, Decimal("33.334"))],
        )
        assert total(lines) == Decimal("0.10")

    def test_keeps_percentage_on_the_line(self):
        lines = split_percentage(Decimal("50.00"), [(1, Decimal("70")), (2, Decimal("30"))])
        assert lines[0].percentage == Decimal("70")
        assert lines[0].amount == Decimal("35.00")


class TestShares:
    def test_weighted(self):
        lines = split_shares(
            Decimal("120.00"), [(1, Decimal("1")), (2, Decimal("1")), (3, Decimal("2"))]
        )
        assert {line.user_id: line.amount for line in lines} == {
            1: Decimal("30.00"),
            2: Decimal("30.00"),
            3: Decimal("60.00"),
        }

    def test_zero_share_participant_pays_nothing(self):
        lines = split_shares(
            Decimal("100.00"), [(1, Decimal("0")), (2, Decimal("1")), (3, Decimal("2"))]
        )
        by_id = {line.user_id: line.amount for line in lines}
        assert by_id[1] == Decimal("0.00")
        assert total(lines) == Decimal("100.00")

    def test_rejects_all_zero_shares(self):
        with pytest.raises(ValidationError) as exc:
            split_shares(Decimal("100.00"), [(1, Decimal("0")), (2, Decimal("0"))])
        assert exc.value.error_code == "INVALID_SHARES"


class TestBuildSplits:
    def test_dispatches_and_balances(self):
        lines = build_splits(
            "equal", Decimal("100.00"), [{"user_id": 1}, {"user_id": 2}, {"user_id": 3}]
        )
        assert total(lines) == Decimal("100.00")

    def test_rejects_unknown_type(self):
        with pytest.raises(ValidationError):
            build_splits("magic", Decimal("10.00"), [{"user_id": 1}])

    def test_missing_field_for_type(self):
        with pytest.raises(ValidationError) as exc:
            build_splits("exact", Decimal("10.00"), [{"user_id": 1}])
        assert exc.value.error_code == "MISSING_SPLIT_FIELD"
