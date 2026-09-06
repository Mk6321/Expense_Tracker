# Splitwave — Group Expense Tracker

Split expenses across a group and always know the answer to one question:

> **How much do I owe, and who do I need to pay?**

React + TypeScript on the front, FastAPI + PostgreSQL behind it, with every rupee
of arithmetic done once — in the backend, in exact decimal.

---

## Running it locally

You need Python 3.10+ and Node 20+.

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate          # Windows;  source .venv/bin/activate elsewhere
pip install -r requirements-dev.txt
cp ../.env.example .env         # fill in DATABASE_URL and JWT_SECRET
alembic upgrade head
uvicorn app.main:app --reload
```

API on http://localhost:8000, interactive docs at `/docs`.

If you have Docker, `docker compose up -d db` gives you a local Postgres on 5432
instead of pointing at Supabase.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env            # VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

App on http://localhost:5173.

### Tests

```bash
cd backend  && pytest                        # 138 tests
cd frontend && npm test                      # 35 tests
```

The backend suite runs on in-memory SQLite by default so it needs no database.
Point `TEST_DATABASE_URL` at a real Postgres to run the identical suite against
`NUMERIC` and `JSONB` for real.

---

## How it is put together

```
React (Vercel) --HTTPS/JSON--> FastAPI (Render) --SQLAlchemy--> PostgreSQL (Supabase)
```

```
backend/app/
  api/v1/        thin route handlers — parse, call a service, return
  services/      all business logic, including the three calculation engines
  repositories/  database queries, no business logic
  models/        SQLAlchemy ORM
  schemas/       Pydantic request/response models
  core/          config, security, dependencies, error envelope

frontend/src/
  features/{auth,groups,expenses,settlements,reports}/
  components/    shared UI kit
  lib/           api client, query hooks, decimal helpers
```

### The decisions that matter

**Money is never a float.** `NUMERIC(12,2)` in Postgres, `Decimal` in Python,
and a JSON **string** on the wire — `"33.34"`, never `33.34`. The frontend uses
decimal.js for any display arithmetic. SQLite (test path only) stores money as
text, because its numeric type would quietly round through a float.

**One calculation engine.** `split_service`, `balance_service` and
`settlement_service` are pure functions with no database or HTTP imports, so they
are unit-tested directly. The frontend never computes a balance; it renders what
the API returns.

**Splits are always recomputed server-side.** Whatever amounts a client sends,
the server rebuilds them from the split type and re-checks that they sum to the
expense total to the cent before anything is written.

**Remainders are deterministic.** A ₹100 three-way split is 33.34 / 33.33 / 33.33,
and the extra cent goes to the lowest `user_id` — not to whoever happens to be
first in the list, and not to a different person if you reorder the request.

**Group access 404s, never 403s.** One FastAPI dependency gates every
group-scoped route. A group you are not in is indistinguishable from one that
does not exist, so ids cannot be probed.

**Nothing is deleted.** Expenses and settlements are reversed (`is_reversed`),
members are marked `removed`, groups are archived. Balances exclude reversed
rows; the history stays intact and every financial mutation writes an audit log
entry in the same transaction.

**Concurrent edits conflict loudly.** `PUT /expenses/{id}` requires the `version`
you read and returns 409 if someone else got there first.

**Retries do not double-charge.** Expense and settlement creation accept an
`Idempotency-Key` header and replay the stored response.

### Both settlement views

The simplified plan minimises transfers, but it can pair two people who never
shared an expense — which users find baffling. So the API returns the
unsimplified pairwise ledger alongside it, and the Settle-up screen lets you
switch between them.

---

## Deploying

Step by step in **[DEPLOYMENT.md](DEPLOYMENT.md)**. The short version:

| Piece    | Host     | Notes                                                       |
| -------- | -------- | ----------------------------------------------------------- |
| Frontend | Vercel   | `vercel.json` at the root; set `VITE_API_BASE_URL`          |
| Backend  | Render   | `render.yaml` blueprint, root `backend`                     |
| Database | Supabase | Transaction pooler (6543) for the app, session (5432) for Alembic |

The thing that will cost you an afternoon otherwise: Supabase's **direct**
connection host (`db.<ref>.supabase.co`) resolves to **IPv6 only**, and Render's
free tier has no IPv6 outbound. Use the pooler hosts, which are IPv4 — and note
their username is `postgres.<project-ref>`, not `postgres`.

Also:

- Alembic needs the **session** pooler (5432). Transaction mode gives a
  different backend per statement, which breaks DDL — hence the separate
  `DATABASE_URL_MIGRATIONS`.
- Keep the SQLAlchemy pool small (3–5); Supabase's free tier caps connections.
- Vercel and Render are different origins, so the refresh cookie needs
  `SameSite=None; Secure` and CORS needs `allow_credentials=True` with an
  explicit origin list — never `*`.

Render's free tier sleeps after inactivity and takes 30–50s to wake. The app
says so explicitly on a slow first load rather than showing a spinner that looks
broken.

---

## Not built yet

Deliberately out of scope for now: receipt attachments and OCR, recurring
expenses, notifications, real-time sync, multi-currency conversion, and offline
support. The `attachments` table exists so the migration history stays stable,
but nothing writes to it.
