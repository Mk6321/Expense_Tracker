"""Pure split maths. No DB, no FastAPI, no I/O -- everything here is a function of
its arguments so it can be unit-tested directly (Section 8).

Every amount is a Decimal. There is not a float anywhere in this module, and there
must never be one: 0.1 + 0.2 is how a ledger silently stops balancing.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Iterable, Sequence

from app.core.errors import ValidationError
from app.models.enums import SplitType

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
HUNDRED = Decimal("100")


@dataclass(frozen=True)
class SplitLine:
    user_id: int
    amount: Decimal
    percentage: Decimal | None = None
    shares: Decimal | None = None


def quantize_money(value: Decimal) -> Decimal:
    """2dp, half-up per line item (Section 6) -- explicitly not banker's rounding."""
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def to_cents(value: Decimal) -> int:
    return int((Decimal(value) * 100).to_integral_value(rounding=ROUND_HALF_UP))


def from_cents(cents: int) -> Decimal:
    return (Decimal(cents) / 100).quantize(CENT)


def allocate_largest_remainder(
    total: Decimal, weights: Sequence[tuple[int, Decimal]]
) -> dict[int, Decimal]:
    """Split total across weighted participants using the largest-remainder method.

    Each participant's exact share is floored to whole cents; the leftover cents are
    handed out one at a time to the largest fractional remainders, ties broken by
    ascending user_id. Deterministic, order-independent, and always sums to total
    to the cent -- never "give the remainder to whoever is first in the list".
    """
    if not weights:
        raise ValidationError("At least one participant is required.", "NO_PARTICIPANTS")

    total_weight = sum((w for _, w in weights), ZERO)
    if total_weight <= 0:
        raise ValidationError("Total weight must be greater than zero.", "INVALID_WEIGHTS")

    total_cents = to_cents(total)
    rows: list[list] = []  # [user_id, whole_cents, fractional_remainder]
    for user_id, weight in weights:
        if weight < 0:
            raise ValidationError("Weights cannot be negative.", "INVALID_WEIGHTS")
        exact = (Decimal(total_cents) * weight) / total_weight
        floored = int(exact.to_integral_value(rounding=ROUND_FLOOR))
        rows.append([user_id, floored, exact - floored])

    leftover = total_cents - sum(r[1] for r in rows)
    if leftover:
        step = 1 if leftover > 0 else -1
        # Largest remainder first; ascending user_id breaks ties. If we ever have to
        # claw a cent back we walk the same order from the other end, so the result
        # stays deterministic in both directions.
        order = sorted(range(len(rows)), key=lambda i: (-rows[i][2], rows[i][0]))
        if step < 0:
            order.reverse()
        for n in range(abs(leftover)):
            rows[order[n % len(order)]][1] += step

    return {user_id: from_cents(cents) for user_id, cents, _ in rows}


def _validate_participants(user_ids: Iterable[int]) -> list[int]:
    ids = list(user_ids)
    if not ids:
        raise ValidationError("At least one participant is required.", "NO_PARTICIPANTS")
    if len(set(ids)) != len(ids):
        raise ValidationError("A participant may only appear once.", "DUPLICATE_PARTICIPANT")
    return ids


def _validate_total(total: Decimal) -> Decimal:
    total = quantize_money(total)
    if total <= ZERO:
        raise ValidationError("Amount must be greater than zero.", "INVALID_AMOUNT")
    return total


def split_equal(total: Decimal, user_ids: Sequence[int]) -> list[SplitLine]:
    total = _validate_total(total)
    ids = _validate_participants(user_ids)
    allocation = allocate_largest_remainder(total, [(uid, Decimal(1)) for uid in ids])
    return [SplitLine(user_id=uid, amount=allocation[uid]) for uid in ids]


def split_exact(total: Decimal, amounts: Sequence[tuple[int, Decimal]]) -> list[SplitLine]:
    total = _validate_total(total)
    _validate_participants(uid for uid, _ in amounts)

    lines: list[SplitLine] = []
    running = ZERO
    for user_id, raw in amounts:
        amount = quantize_money(raw)
        if amount < ZERO:
            raise ValidationError("Split amounts cannot be negative.", "INVALID_SPLIT_AMOUNT")
        running += amount
        lines.append(SplitLine(user_id=user_id, amount=amount))

    if running != total:
        raise ValidationError(
            f"Splits total {running} but the expense is {total}.", "SPLIT_SUM_MISMATCH"
        )
    return lines


def split_percentage(
    total: Decimal, percentages: Sequence[tuple[int, Decimal]]
) -> list[SplitLine]:
    total = _validate_total(total)
    ids = _validate_participants(uid for uid, _ in percentages)

    pct_sum = ZERO
    for _, raw in percentages:
        pct = Decimal(raw)
        if pct < ZERO:
            raise ValidationError("Percentages cannot be negative.", "INVALID_PERCENTAGE")
        pct_sum += pct
    if pct_sum != HUNDRED:
        raise ValidationError(
            f"Percentages must sum to 100 (got {pct_sum}).", "PERCENTAGE_SUM_MISMATCH"
        )

    weights = [(uid, Decimal(pct)) for uid, pct in percentages]
    allocation = allocate_largest_remainder(total, weights)
    pct_by_id = {uid: Decimal(pct) for uid, pct in percentages}
    return [
        SplitLine(user_id=uid, amount=allocation[uid], percentage=pct_by_id[uid]) for uid in ids
    ]


def split_shares(total: Decimal, shares: Sequence[tuple[int, Decimal]]) -> list[SplitLine]:
    total = _validate_total(total)
    ids = _validate_participants(uid for uid, _ in shares)

    share_sum = ZERO
    for _, raw in shares:
        share = Decimal(raw)
        if share < ZERO:
            raise ValidationError("Shares cannot be negative.", "INVALID_SHARES")
        share_sum += share
    if share_sum <= ZERO:
        raise ValidationError("Total shares must be greater than zero.", "INVALID_SHARES")

    allocation = allocate_largest_remainder(total, [(uid, Decimal(s)) for uid, s in shares])
    shares_by_id = {uid: Decimal(s) for uid, s in shares}
    return [
        SplitLine(user_id=uid, amount=allocation[uid], shares=shares_by_id[uid]) for uid in ids
    ]


def build_splits(
    split_type: str,
    total: Decimal,
    participants: Sequence[dict],
) -> list[SplitLine]:
    """Dispatch to the right split function.

    participants is a list of {user_id, amount?, percentage?, shares?}. Whatever the
    client sent, the returned lines are recomputed here and are guaranteed to sum to
    total -- the API layer never trusts client-supplied amounts.
    """
    if split_type == SplitType.EQUAL.value:
        lines = split_equal(total, [p["user_id"] for p in participants])
    elif split_type == SplitType.EXACT.value:
        lines = split_exact(
            total, [(p["user_id"], _require(p, "amount", split_type)) for p in participants]
        )
    elif split_type == SplitType.PERCENTAGE.value:
        lines = split_percentage(
            total, [(p["user_id"], _require(p, "percentage", split_type)) for p in participants]
        )
    elif split_type == SplitType.SHARES.value:
        lines = split_shares(
            total, [(p["user_id"], _require(p, "shares", split_type)) for p in participants]
        )
    else:
        raise ValidationError(f"Unknown split type '{split_type}'.", "INVALID_SPLIT_TYPE")

    assert_splits_balance(total, lines)
    return lines


def _require(participant: dict, field: str, split_type: str) -> Decimal:
    value = participant.get(field)
    if value is None:
        raise ValidationError(
            f"Each participant needs a '{field}' for a {split_type} split.",
            "MISSING_SPLIT_FIELD",
        )
    return Decimal(str(value))


def assert_splits_balance(total: Decimal, lines: Sequence[SplitLine]) -> None:
    """The Section 1 non-negotiable, enforced server-side on every create and update."""
    line_sum = sum((line.amount for line in lines), ZERO)
    if line_sum != quantize_money(total):
        raise ValidationError(
            f"Splits total {line_sum} but the expense is {total}.", "SPLIT_SUM_MISMATCH"
        )
