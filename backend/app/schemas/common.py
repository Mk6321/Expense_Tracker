from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Any, Generic, TypeVar

from pydantic import BaseModel, BeforeValidator, ConfigDict, PlainSerializer

T = TypeVar("T")


def _to_decimal(value: Any) -> Any:
    """Accept "12.50", 12.5 or Decimal on the way in; never keep a float around."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, str):
        return Decimal(value.strip())
    return value


def _money_str(value: Decimal) -> str:
    return str(Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# Money crosses the wire as a JSON *string* (Section 6) -- "33.34", never 33.34.
Money = Annotated[
    Decimal,
    BeforeValidator(_to_decimal),
    PlainSerializer(_money_str, return_type=str, when_used="json"),
]

# Percentages and share counts are exact too, just not currency-shaped.
Rate = Annotated[
    Decimal,
    BeforeValidator(_to_decimal),
    PlainSerializer(lambda v: str(Decimal(v).normalize()), return_type=str, when_used="json"),
]


class AppModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class Envelope(BaseModel, Generic[T]):
    """The Section 7 response envelope. Every route returns one of these."""

    success: bool = True
    data: T | None = None
    message: str | None = None


class ErrorEnvelope(BaseModel):
    success: bool = False
    data: None = None
    message: str
    error_code: str


class Page(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None
