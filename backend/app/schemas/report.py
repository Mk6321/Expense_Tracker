from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common import AppModel, Money


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    icon: str | None = Field(default=None, max_length=40)


class CategoryOut(AppModel):
    id: int
    group_id: int | None
    name: str
    icon: str | None
    is_active: bool
    created_at: datetime


class SummaryOut(BaseModel):
    group_id: int
    currency: str
    total_spend: Money
    expense_count: int
    member_count: int
    my_total_paid: Money
    my_total_share: Money
    my_balance: Money
    average_expense: Money
    largest_expense: Money
    first_expense_date: date | None = None
    last_expense_date: date | None = None


class CategoryReportRow(BaseModel):
    category_id: int | None
    category_name: str
    icon: str | None = None
    total: Money
    expense_count: int
    percentage: str


class MemberReportRow(BaseModel):
    user_id: int
    name: str
    total_paid: Money
    total_share: Money
    balance: Money
    expense_count: int


class MonthlyReportRow(BaseModel):
    month: str  # YYYY-MM
    total: Money
    expense_count: int
    my_share: Money
