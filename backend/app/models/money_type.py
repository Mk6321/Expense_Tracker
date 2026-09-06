from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Numeric, String
from sqlalchemy.types import TypeDecorator


class SqliteDecimal(TypeDecorator):
    """Stores a Decimal as text on SQLite.

    SQLite has no exact numeric type -- SQLAlchemy would round-trip NUMERIC through
    a float, which is precisely the thing this project forbids. Postgres uses real
    NUMERIC(12,2); this variant only exists so the test suite can run offline and
    still be exact to the cent.
    """

    impl = String(32)
    cache_ok = True

    def __init__(self, scale: int = 2, **kwargs):
        self.scale = scale
        self._exp = Decimal(1).scaleb(-scale)
        super().__init__(**kwargs)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(Decimal(value).quantize(self._exp))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return Decimal(value)


def money_column(precision: int = 12, scale: int = 2):
    return Numeric(precision, scale).with_variant(SqliteDecimal(scale=scale), "sqlite")
