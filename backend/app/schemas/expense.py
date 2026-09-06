from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import SplitType
from app.schemas.common import AppModel, Money, Rate


class ParticipantIn(BaseModel):
    """One participant of an expense. Which of amount/percentage/shares is required
    depends on the split type; the split engine validates that, not this schema."""

    user_id: int
    amount: Money | None = None
    percentage: Rate | None = None
    shares: Rate | None = None


class ExpenseBase(BaseModel):
    description: str = Field(min_length=1, max_length=255)
    amount: Money = Field(gt=0)
    expense_date: date
    split_type: SplitType = SplitType.EQUAL
    category_id: int | None = None
    notes: str | None = Field(default=None, max_length=2000)
    paid_by: int
    participants: list[ParticipantIn] = Field(min_length=1)

    @model_validator(mode="after")
    def _no_duplicate_participants(self) -> "ExpenseBase":
        ids = [p.user_id for p in self.participants]
        if len(set(ids)) != len(ids):
            raise ValueError("A participant may only appear once.")
        return self


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseUpdate(ExpenseBase):
    # Optimistic lock: the client must send back the version it read (Section 4).
    version: int = Field(ge=1)


class SplitOut(AppModel):
    user_id: int
    amount: Money
    percentage: Rate | None = None
    shares: Rate | None = None


class ExpenseOut(AppModel):
    id: int
    group_id: int
    description: str
    amount: Money
    currency: str
    paid_by: int
    paid_by_name: str | None = None
    category_id: int | None
    category_name: str | None = None
    expense_date: date
    split_type: str
    notes: str | None
    created_by: int
    version: int
    is_reversed: bool
    reversed_by: int | None = None
    reversed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    splits: list[SplitOut] = []
    # What the current user's involvement in this expense nets out to.
    my_share: Money | None = None
