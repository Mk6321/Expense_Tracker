# How Splitwave works

A complete walk through the system: what happens on every request, how groups and
categories come into existence, and exactly how every number on screen is
calculated.

All the arithmetic below is worked with the real data in the demo group
**Flat 3B** (Alice, Bob, Cara), so you can check any of it against the live app.

---

## Contents

1. [The shape of a request](#1-the-shape-of-a-request)
2. [Money: why none of it is a float](#2-money-why-none-of-it-is-a-float)
3. [Accounts and sessions](#3-accounts-and-sessions)
4. [Groups](#4-groups)
5. [Invites and joining](#5-invites-and-joining)
6. [Members and roles](#6-members-and-roles)
7. [Categories](#7-categories)
8. [Creating an expense](#8-creating-an-expense)
9. [The split engine](#9-the-split-engine)
10. [Editing and reversing](#10-editing-and-reversing)
11. [The balance engine](#11-the-balance-engine)
12. [The pairwise ledger](#12-the-pairwise-ledger)
13. [Settlement suggestions](#13-settlement-suggestions)
14. [Recording a settlement](#14-recording-a-settlement)
15. [Reports](#15-reports)
16. [The audit log](#16-the-audit-log)
17. [Idempotency](#17-idempotency)
18. [The security model](#18-the-security-model)
19. [Where everything lives](#19-where-everything-lives)

---

## 1. The shape of a request

```
Browser  ──HTTPS/JSON──▶  FastAPI  ──SQLAlchemy──▶  PostgreSQL
(Vercel)                  (Render)                  (Supabase)
```

Inside the backend, every request goes through the same four layers, and each one
has exactly one job:

```
api/          Parse the request. Call a service. Return the answer.
services/     All the business logic and every calculation.
repositories/ Database queries. No decisions, no arithmetic.
models/       The SQLAlchemy tables.
```

The rule that keeps this honest: **if a route handler contains an `if` that
decides a financial outcome, it is in the wrong file.** Routes are deliberately
boring.

Every response has the same envelope:

```json
{ "success": true,  "data": { }, "message": null }
{ "success": false, "data": null, "message": "User does not belong to this group.",
  "error_code": "GROUP_ACCESS_DENIED" }
```

The frontend never has to guess whether something worked. It reads `success`, and
on failure it has a stable `error_code` to branch on and a `message` safe to show
a person. Stack traces are logged on the server and never sent to the browser.

**The frontend calculates nothing.** It has no idea how a balance is derived. It
renders strings the API hands it. This is the single most important architectural
decision in the project: there is exactly one place where money maths happens, so
there is exactly one place for it to be wrong, and one place to test.

---

## 2. Money: why none of it is a float

A float cannot represent 0.10 exactly. Add enough of them and a ledger silently
stops balancing — the classic `0.1 + 0.2 = 0.30000000000000004`. So money is
never a float anywhere in this system:

| Layer      | Type                          |
| ---------- | ----------------------------- |
| PostgreSQL | `NUMERIC(12,2)`               |
| Python     | `decimal.Decimal`             |
| JSON       | a **string**, `"33.34"`       |
| TypeScript | `string`, and `Decimal` for maths |

That JSON detail matters more than it looks. If the API sent `33.34` as a JSON
number, `JSON.parse` would turn it into a float the moment it arrived and the
guarantee would be lost at the last step. So Pydantic serialises every `Decimal`
as a string, and the TypeScript types declare every money field as `string` — you
cannot accidentally do `a + b` on two of them and get a sensible-looking wrong
answer, because that would produce `"33.3433.34"`.

Where the browser genuinely needs arithmetic — the live "left to allocate" figure
while you type a custom split — it uses **decimal.js**, never native numbers.

**Rounding** is half-up to 2 decimal places, per line item. Not banker's
rounding.

> **Testing note.** SQLite has no exact numeric type, so the offline test suite
> would have round-tripped money through a float. `app/models/money_type.py`
> stores money as text on SQLite only. Postgres uses real `NUMERIC(12,2)`.

---

## 3. Accounts and sessions

### Registering

`POST /api/v1/auth/register` with a name, email and password (minimum 8
characters).

The password is hashed with **Argon2** — the current recommendation for password
hashing, deliberately slow and memory-hard so that a stolen database is not a
stolen list of passwords. The plaintext is never stored, never logged, and never
returned.

### Logging in

`POST /api/v1/auth/login` returns two tokens that behave very differently:

| Token       | Lifetime | Stored where                            | Why                                     |
| ----------- | -------- | --------------------------------------- | --------------------------------------- |
| **Access**  | 15 min   | JavaScript memory only                  | Short-lived, so a leak expires fast     |
| **Refresh** | 14 days  | `httpOnly; Secure; SameSite=None` cookie | JavaScript literally cannot read it     |

Neither ever touches `localStorage`. An XSS bug on the page cannot steal the
refresh token, because `httpOnly` means the browser will not hand it to script at
all — it only attaches it to requests automatically.

One deliberate detail: **a wrong password and an unknown email return an
identical error**, and the server hashes a dummy password when the account does
not exist so the two paths take the same time. Otherwise the login form doubles
as a way to find out who has an account.

### Staying logged in

The access token lives in memory, so a page refresh loses it. On boot the app
calls `POST /auth/refresh` once; the browser sends the cookie automatically, and
a new access token comes back. If it fails you see the login screen.

**Refresh tokens rotate**: every refresh issues a brand-new token with a new `jti`
and replaces the cookie. When an access token expires mid-session, the axios
interceptor catches the 401, refreshes, and replays the original request — you
never notice. Parallel 401s collapse into a single refresh call rather than a
stampede.

---

## 4. Groups

A group is a shared ledger. It has a name, a currency, and members.

**Creating one** (`POST /api/v1/groups`) does three things in one transaction:

1. Insert the group.
2. Add the creator as a member with role **admin**.
3. Write an audit-log entry.

One transaction, so a group can never exist without an admin.

The currency is set once, at the top of the group, and every expense inherits it.
There is no per-expense currency and no conversion — multi-currency is explicitly
out of scope, and pretending otherwise would mean storing exchange rates and
deciding *when* to apply them, which is a genuinely hard problem, not a small
feature.

**Deleting a group archives it.** `DELETE /api/v1/groups/{id}` sets
`is_archived = true`. Archived groups reject new expenses but stay fully
readable. Financial history is never destroyed in this system, ever.

The current group lives in the URL — `/groups/1/dashboard` — not in component
state, so refreshing the page or sharing a link lands in the right place.

---

## 5. Invites and joining

You do not add people to a group by typing their email. You generate a code and
they redeem it.

**`POST /api/v1/groups/{id}/invites`** (admin only) creates an 8-character code
from an unambiguous alphabet — `ABCDEFGHJKLMNPQRSTUVWXYZ23456789`. No `I`, `O`,
`0` or `1`, because these codes get read aloud and typed from a screenshot. That
gives 32⁸ ≈ 1.1 trillion combinations; the code is generated with
`secrets.choice`, and if one somehow collides with an existing code the server
retries rather than failing.

Codes expire after **7 days** (configurable) and an admin can revoke one early.

**`POST /api/v1/groups/join`** with `{ "invite_code": "..." }` checks, in order:

1. The code exists → else 404 `INVITE_INVALID`
2. It has not been revoked → else 422 `INVITE_REVOKED`
3. It has not expired → else 422 `INVITE_EXPIRED`
4. The group is not archived → else 422 `GROUP_ARCHIVED`
5. You are not already a member → else 409 `ALREADY_MEMBER`

Codes are case-insensitive and whitespace-trimmed on the way in.

**Rejoining is special.** If you were removed from the group and come back with a
new code, the system *reactivates your original membership row* rather than
creating a new one. Your old expense splits stay attached to the same membership,
so your history is continuous instead of forking into a second identity.

---

## 6. Members and roles

Three roles:

| Role       | Can do                                                                   |
| ---------- | ------------------------------------------------------------------------ |
| **Admin**  | Everything: manage the group, members, categories; edit or reverse *any* expense |
| **Member** | Add expenses, record settlements; edit or reverse **only what they created** |
| **Viewer** | Read-only — balances and reports, no writes at all                        |

The write check on an expense is exactly:

```
expense.created_by == current_user.id  OR  current_user.role == "admin"
```

A settlement can be reversed by **either party involved**, or an admin.

### Removing someone

`DELETE /api/v1/groups/{id}/members/{user_id}` does **not** delete the row. It
sets `status = 'removed'`.

This is not squeamishness — it is a foreign-key necessity. That person's `user_id`
appears on every expense split they were ever part of. Delete the row and either
those splits break, or you cascade-delete them and silently change everyone
else's balance. So the row stays, their name still resolves on old expenses, and
they simply lose access.

**Removal is blocked while their balance is not zero** (409
`MEMBER_HAS_BALANCE`). Letting someone walk out mid-debt would leave a permanent
hole in the ledger. An admin can override with `?force=true`, and the audit log
records the exact balance at the moment of removal, so the debt is documented
rather than vanished.

One more guard: **the last admin cannot be demoted or removed.** A group without
an admin can never be administered again.

---

## 7. Categories

Categories come from two places, and the distinction is the whole design.

### Global defaults

Ten categories are seeded once, on first API boot, with `group_id = NULL`:

> Food & Drink · Groceries · Rent · Utilities · Transport · Entertainment ·
> Travel · Shopping · Health · Other

`group_id = NULL` means *not owned by any group, available to all of them*. The
seed is idempotent — it checks which names already exist and only inserts what is
missing — so it is safe on every restart and every redeploy.

### Group categories

An admin can add their own via `POST /api/v1/groups/{id}/categories`. These get
`group_id` set to that group.

Listing categories returns `group_id IS NULL OR group_id = <this group>`, so each
group sees the ten shared defaults plus its own. In the UI the group's own
categories are tinted purple and the shared defaults grey.

**Cross-group leakage is blocked explicitly.** When you save an expense with a
`category_id`, the server checks that the category is either global or belongs to
*this* group. Passing another group's category id returns 422
`CATEGORY_NOT_FOUND` — you cannot use a valid id you happen to know about to
discover anything about another group.

A category is optional. An expense without one reports as "Uncategorised".

---

## 8. Creating an expense

`POST /api/v1/groups/{id}/expenses`. You send a description, an amount, a date,
who paid, a split type, and a list of participants.

The server runs these gates **in order**, and every one of them is enforced
server-side regardless of what the client believes:

1. **Are you a member of this group?** If not — 404, not 403. (See §18.)
2. **Are you allowed to write?** Viewers get 403 `READ_ONLY_ROLE`.
3. **Is the group archived?** Archived groups reject new expenses.
4. **Is the payer a member?** Else 422 `PAYER_NOT_MEMBER`.
5. **Is every participant a member?** Else 422 `PARTICIPANT_NOT_MEMBER`.
   Without this, someone could quietly attach a stranger's user id to a split.
6. **Is the category valid for this group?** (see §7)
7. **Compute the splits** — see §9.
8. **Do the splits sum exactly to the total?** To the cent, or nothing is saved.

Then the expense, all its split rows, and an audit-log entry are written in a
**single transaction**. There is no window in which an expense exists without its
splits.

### Client amounts are never trusted

This is worth stating plainly. If you send `split_type: "equal"` along with a
participant list claiming Alice owes ₹1 and Bob owes ₹99, the server **throws
your numbers away** and recomputes an equal split. The split type determines the
result; the client's arithmetic is only ever a suggestion for the preview.

---

## 9. The split engine

Four split types, all pure functions in `services/split_service.py` — no
database, no HTTP, so they are unit-tested directly.

### Equal

Total ÷ number of participants, with the remainder handled by the
largest-remainder method below.

### Exact

You supply each amount. Rejected with `SPLIT_SUM_MISMATCH` if they do not sum to
the total.

### Percentage

You supply each percentage. Rejected with `PERCENTAGE_SUM_MISMATCH` if they do
not sum to exactly 100, then converted to amounts.

### Shares

You supply share counts, which can be zero. Rejected if the total is ≤ 0.

---

### The largest-remainder method

₹100 does not divide into three. This is where most expense trackers quietly lose
a cent, or always give it to whoever happens to be first in the list.

The rule here:

1. Convert the total to whole cents.
2. Give everyone their exact fractional share, **rounded down**.
3. Count the leftover cents.
4. Hand them out one at a time, to the **largest fractional remainders first**.
5. Break ties by **ascending `user_id`**.

**Worked example — "Dinner at Toit", ₹100.00, equal, three people:**

```
Total in cents                       10000
Exact share each        10000 / 3  =  3333.333…
Floor each                         =  3333       (₹33.33)
Sum of floors           3333 × 3   =  9999
Leftover                                    1 cent

All three remainders tie at .333, so the tiebreak is user_id ascending.
Alice is user 1 → Alice gets the extra cent.
```

Result: **Alice ₹33.34, Bob ₹33.33, Cara ₹33.33 → exactly ₹100.00.**

Two properties follow, and both are tested:

- **Deterministic.** The same expense always splits the same way.
- **Order-independent.** Sending the participants as `[3, 1, 2]` gives Alice the
  extra cent just the same. The result depends on who is involved, not on the
  order your client happened to serialise them.

**Worked example — "Groceries", ₹2450.75, shares 1 : 1 : 2:**

```
Total in cents                              245075
Total shares                                     4

Alice  245075 × 1/4 = 61268.75  → floor 61268, remainder .75
Bob    245075 × 1/4 = 61268.75  → floor 61268, remainder .75
Cara   245075 × 2/4 = 122537.50 → floor 122537, remainder .50

Sum of floors = 245073          → leftover 2 cents

Order by (largest remainder, then lowest user_id):
  Alice (.75, id 1) → +1
  Bob   (.75, id 2) → +1
  Cara  (.50, id 3) → nothing
```

Result: **Alice ₹612.69, Bob ₹612.69, Cara ₹1225.37 → exactly ₹2450.75.**

Note Cara pays double as her 2 shares dictate, and the two leftover cents went to
the two people with the larger fractional claim — not to whoever was first.

---

## 10. Editing and reversing

### Editing, and the version check

`PUT /api/v1/expenses/{id}` requires the `version` number you read when you
opened the expense.

If two people open the same expense and both save, the second one's `version` no
longer matches what is in the database, and they get **409 `VERSION_CONFLICT`**
instead of silently overwriting the first person's edit. The UI translates that
into: *"Someone else edited this expense while you had it open."*

Every successful update increments `version` and rewrites **all** the split rows
from scratch. There is no partial-split edit path, which is what makes the
sum-equals-total invariant trivially checkable on every write.

### Reversing

`DELETE /api/v1/expenses/{id}` does not delete anything. It sets:

```
is_reversed = true
reversed_by = <who did it>
reversed_at = <when>
```

The expense and every one of its splits stay in the database. Balance
calculations simply exclude reversed rows. You can still open the expense and see
exactly what it was, who created it, and who reversed it.

Reversing is idempotent-safe: a second attempt returns 422 `ALREADY_REVERSED`
rather than doing it twice. A reversed expense cannot be edited.

---

## 11. The balance engine

Balances are **never stored**. There is no `balance` column anywhere in the
schema, by design — a stored balance is a number that can drift from the rows it
claims to summarise, and once it drifts you cannot tell which one is lying.

Every balance is recomputed from source rows on every request, using only
non-reversed expenses and non-reversed settlements.

For each member:

```
total_paid            = sum of expenses they paid for
total_share           = sum of their split lines
settlements_paid      = money they handed over
settlements_received  = money handed to them

balance = total_paid − total_share + settlements_paid − settlements_received
```

**Positive means the group owes you. Negative means you owe the group.**

Settlements sit in that formula rather than modifying expenses, because paying
someone back does not change what dinner cost. They are a separate ledger entry
that nets against the expense side.

### Worked example — the real Flat 3B numbers

Five expenses, plus one settlement of ₹12,096.53 from Alice to Bob.

| Member | `total_paid` | `total_share` | `s_paid`  | `s_recv`  | **balance**   |
| ------ | -----------: | ------------: | --------: | --------: | ------------: |
| Alice  |     1,999.00 |     13,428.87 | 12,096.53 |      0.00 |   **+666.66** |
| Bob    |    36,000.00 |     13,428.85 |      0.00 | 12,096.53 | **+10,474.62** |
| Cara   |     2,450.75 |     13,592.03 |      0.00 |      0.00 | **−11,141.28** |

Alice's line, step by step:

```
  1,999.00   paid  (100.00 dinner + 899.00 cab + 1000.00 zepto)
− 13,428.87  her share of all five expenses
+ 12,096.53  she already paid Bob back
─────────────
     666.66  the group owes Alice
```

**The invariant: balances always sum to exactly 0.00.**

```
666.66 + 10,474.62 − 11,141.28 = 0.00
```

Every rupee someone paid is a rupee someone owes. If that sum is ever non-zero,
something is broken — which is why it is asserted in the test suite for every
scenario, not just checked once.

---

## 12. The pairwise ledger

The balance table says *how much* each person is up or down. It does not say
*who* should pay *whom*. Two different answers to that exist, and the app shows
both.

The **pairwise ledger** is the honest one: for every expense, each participant
owes the payer their share. Opposite debts between the same two people cancel
out, and settlements reduce what one owes the other.

For Flat 3B:

```
Alice → Cara       246.03
Bob   → Alice      912.69
Cara  → Bob     11,387.31
```

Working the Alice/Cara pair by hand:

```
Cara owes Alice   33.33  (dinner)
              + 333.33  (zepto)
              = 366.66

Alice owes Cara  612.69  (groceries)

Net:  612.69 − 366.66 = 246.03,  Alice owes Cara
```

Every line here traces back to something the two of them actually shared.

---

## 13. Settlement suggestions

The pairwise ledger is truthful but inefficient — it can produce a lot of small
transfers. The **simplified plan** minimises the number of payments.

The algorithm is greedy creditor/debtor matching:

1. Split everyone into debtors (negative balance) and creditors (positive).
2. Sort both by size, largest first, **ascending `user_id` as the tiebreak**.
3. Match the largest debtor against the largest creditor and transfer the smaller
   of the two amounts.
4. Whoever hits zero drops out. Repeat.

For Flat 3B:

```
Debtors:    Cara  11,141.28
Creditors:  Bob   10,474.62
            Alice    666.66

Step 1: Cara → Bob    min(11,141.28, 10,474.62) = 10,474.62
        Cara now owes 666.66;  Bob settled.
Step 2: Cara → Alice  min(666.66, 666.66)       =    666.66
        Both settled.
```

**Two transfers instead of three, and everyone lands on exactly zero.**

The `user_id` tiebreak is what makes this deterministic: the same balances always
produce the same plan, no matter what order the rows came back from the database
in. That is tested by computing a plan, reversing the input order, and asserting
the two plans are identical.

> Greedy matching is not provably optimal — minimising transfers in general is
> NP-hard. It is O(n log n), never produces more than n−1 transfers, and is
> stable, which matters more here than shaving off a hypothetical extra payment.

### Why both views exist

Look at what the two say about Alice and Cara:

| View            | What it says                      |
| --------------- | --------------------------------- |
| Simplified plan | **Cara pays Alice ₹666.66**       |
| Pairwise ledger | **Alice owes Cara ₹246.03**       |

Both are correct. The simplified plan routes Cara's debt to Bob *through* Alice
because it is optimising the whole graph, not that one relationship. But if Cara
only ever sees "pay Alice ₹666.66" she will reasonably ask why she is paying
someone she is actually owed money by.

That is precisely why the Settle-up screen has both tabs. The simplified plan
gets you square in the fewest payments; the detailed view is there when someone
wants to know *why*.

---

## 14. Recording a settlement

`POST /api/v1/groups/{id}/settlements` — who paid, who received, how much, when.

Rules:

- The two parties must be different (422 `SAME_PARTY`).
- Both must belong to the group.
- A **member** can only record a settlement they are part of. An **admin** can
  record one on anyone's behalf (422 `NOT_SETTLEMENT_PARTY` otherwise).

Settlements **never touch expense rows**. They are their own ledger entry, and
the balance formula nets them out. This is tested explicitly: recording a
settlement and re-reading the expense list returns a byte-identical result.

Reversing one (`DELETE /api/v1/settlements/{id}`) is the same soft reversal as
expenses — the row stays, marked `is_reversed`, and balances snap back.

---

## 15. Reports

Four endpoints under `/groups/{id}/reports/`, all excluding reversed rows:

| Endpoint      | What it gives you                                                    |
| ------------- | -------------------------------------------------------------------- |
| `summary`     | Total spend, count, average, largest, your paid/share/balance, date range |
| `categories`  | Total and share-of-spend per category, biggest first                 |
| `members`     | Per-person paid, share, balance, and how many expenses they paid for |
| `monthly`     | Total and your share per calendar month                              |

These are aggregated in Python from the same rows the balance engine reads,
rather than as separate SQL. Groups are small — a handful of members, hundreds of
expenses — and the alternative is a second definition of "spend" written in SQL
that can drift out of step with the first one. One definition, one place to fix.

---

## 16. The audit log

Every financial mutation writes an `audit_logs` row **inside the same transaction
as the change itself**. If the change rolls back, so does its log entry — there
is no such thing as a logged change that did not happen, or a change with no log.

Each entry records who, what entity, what action, and the before/after state as
JSONB.

Logged actions: group create/update/archive, member add/remove/role change,
category create, expense create/update/reverse, settlement create/reverse.

For an expense update, `old_value` and `new_value` hold full snapshots including
every split line — so you can reconstruct exactly what an expense looked like
before someone changed it, and who changed it.

---

## 17. Idempotency

Phone loses signal mid-request. You tap "Add expense" again. Did the first one go
through?

`POST` for expenses and settlements accepts an **`Idempotency-Key`** header. The
frontend generates a fresh UUID per submission attempt. The server:

1. Looks up the key for **this user and this endpoint**.
2. If it has seen it, returns the **stored response** with
   `Idempotency-Replayed: true` and creates nothing.
3. Otherwise creates the record and stores the response against the key.

So a retry returns the same expense, with the same id, and you do not end up
paying for dinner twice. Keys are scoped per user, so two people cannot collide
by chance.

---

## 18. The security model

**Group access returns 404, never 403.** Every group-scoped route depends on one
shared FastAPI dependency, `get_current_group_membership`. If you are not an
active member, you get a 404 that is **byte-identical** to the response for a
group id that does not exist.

A 403 would confirm that a group exists. Someone walking ids would learn how many
groups the system has and when they were created. A 404 tells them nothing. This
is verified in the tests by requesting a real group and a fake one as an outsider
and asserting the two responses are equal.

The rest:

- Argon2 password hashing.
- Access token in memory, refresh token in an `httpOnly` cookie, rotated on use.
- Every group route goes through the one membership dependency — no route
  reimplements the check, so no route can forget it.
- CORS restricted to an explicit origin list. Never `*` — with
  `allow_credentials=True` the browser rejects `*` anyway.
- All queries are parameterised through SQLAlchemy. No string interpolation into
  SQL.
- Passwords, tokens and connection strings are never logged.
- Stack traces are logged server-side; the client gets the generic envelope.

---

## 19. Where everything lives

### The calculations

| File                                | What it owns                                          |
| ----------------------------------- | ----------------------------------------------------- |
| `services/split_service.py`         | All four split types, largest-remainder rounding       |
| `services/balance_service.py`       | Per-user balances, the pairwise ledger                 |
| `services/settlement_service.py`    | Greedy simplification                                  |
| `services/ledger_service.py`        | Loads DB rows and feeds the three engines above        |

The first three are **pure**. No database import, no FastAPI import. Give them
numbers, get numbers back — which is why they can be tested exhaustively without
a server or a database anywhere in sight.

### Everything else

| File                              | What it owns                                 |
| --------------------------------- | -------------------------------------------- |
| `services/auth_service.py`        | Register, login, token rotation              |
| `services/group_service.py`       | Groups, invites, joining, roles, removal     |
| `services/expense_service.py`     | Expense validation, create/update/reverse    |
| `services/settlement_ops.py`      | Settlement writes                            |
| `services/report_service.py`      | The four reports                             |
| `core/deps.py`                    | `get_current_user`, the membership gate      |
| `core/security.py`                | Hashing, JWTs, invite-code generation        |
| `core/idempotency.py`             | Replay handling                              |

### Tests

```bash
cd backend  && pytest      # 138 tests
cd frontend && npm test    # 35 tests
```

The backend suite covers all four split types with rounding edge cases, the eight
critical balance scenarios, cross-group isolation, the optimistic-lock conflict,
idempotency replay, and settlement determinism. It runs on in-memory SQLite by
default, so it needs no database; point `TEST_DATABASE_URL` at Postgres (with
`TEST_DB_SCHEMA` to keep it in its own schema) to run the identical suite against
real `NUMERIC` and `JSONB`.
