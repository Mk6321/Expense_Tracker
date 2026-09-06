from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common import AppModel, Money


class BalanceOut(BaseModel):
    user_id: int
    name: str
    total_paid: Money
    total_share: Money
    settlements_paid: Money
    settlements_received: Money
    balance: Money


class PairwiseDebtOut(BaseModel):
    from_user_id: int
    from_name: str
    to_user_id: int
    to_name: str
    amount: Money


class GroupBalancesOut(BaseModel):
    group_id: int
    currency: str
    balances: list[BalanceOut]
    pairwise: list[PairwiseDebtOut]
    my_balance: Money
    total_outstanding: Money


class SuggestionOut(BaseModel):
    from_user_id: int
    from_name: str
    to_user_id: int
    to_name: str
    amount: Money


class SuggestionsOut(BaseModel):
    group_id: int
    currency: str
    suggestions: list[SuggestionOut]
    pairwise: list[PairwiseDebtOut]
    you_owe: Money
    you_are_owed: Money


class SettlementCreate(BaseModel):
    from_user_id: int
    to_user_id: int
    amount: Money = Field(gt=0)
    settlement_date: date
    notes: str | None = Field(default=None, max_length=2000)


class SettlementOut(AppModel):
    id: int
    group_id: int
    from_user_id: int
    from_name: str | None = None
    to_user_id: int
    to_name: str | None = None
    amount: Money
    settlement_date: date
    notes: str | None
    created_by: int
    created_at: datetime
    is_reversed: bool
    reversed_by: int | None = None
    reversed_at: datetime | None = None
