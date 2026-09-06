# Expense Tracker - Backend

FastAPI + SQLAlchemy (async) + PostgreSQL. All financial logic lives here; the
frontend only renders what these endpoints return.

## Local setup

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows;  source .venv/bin/activate elsewhere
pip install -r requirements-dev.txt
cp ../.env.example .env       # then fill in DATABASE_URL and JWT_SECRET
alembic upgrade head
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

With Docker available, `docker compose up -d db` from the repo root gives you a
local Postgres on 5432 instead of pointing at Supabase.

## Tests

```bash
pytest                                    # runs against in-memory SQLite
TEST_DATABASE_URL=postgresql+asyncpg://... pytest    # runs against real Postgres
```

SQLite has no exact numeric type, so `app/models/money_type.py` stores money as
text on that dialect. Postgres uses real `NUMERIC(12,2)`. Either way nothing ever
becomes a float.

## Layout

```
app/api/v1/       thin route handlers
app/services/     business logic (split, balance, settlement engines)
app/repositories/ database queries only
app/models/       SQLAlchemy ORM
app/schemas/      Pydantic request/response models
app/core/         config, security, dependencies, errors
```

The three pure engines have no DB or HTTP dependency and are unit-tested directly:

- `split_service.py` - equal / exact / percentage / shares, largest-remainder rounding
- `balance_service.py` - per-user balances and the unsimplified pairwise ledger
- `settlement_service.py` - greedy debtor/creditor matching

## Things worth knowing

- Money is `Decimal` everywhere and serialises to JSON as a **string** (`"33.34"`).
- `sum(splits) == expense.amount` is re-checked server-side on every write; client
  amounts are recomputed, never trusted.
- Group access is gated by one dependency (`get_current_group_membership`) that
  returns **404**, not 403, so group ids cannot be probed.
- Nothing is hard-deleted. Expenses and settlements get `is_reversed`; members get
  `status = 'removed'`.
- `PUT /expenses/{id}` requires the `version` you read and 409s if it moved.
- `POST` expense/settlement accept an `Idempotency-Key` header.
