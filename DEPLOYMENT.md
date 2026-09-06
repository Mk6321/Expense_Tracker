# Deploying

Three services: Supabase (database), Render (API), Vercel (frontend). Do them in
that order — Render needs the database URL, and Vercel needs the Render URL.

---

## 0. The connection-string trap (read this first)

Supabase offers three connection strings and they are not interchangeable.

| String          | Host                              | Port | Use it for       |
| --------------- | --------------------------------- | ---- | ---------------- |
| **Direct**      | `db.<ref>.supabase.co`            | 5432 | **Nothing here** |
| **Transaction** | `aws-0-<region>.pooler.supabase.com` | 6543 | The running app  |
| **Session**     | `aws-0-<region>.pooler.supabase.com` | 5432 | Alembic          |

The direct host resolves to an **IPv6 address only** on current Supabase
projects. Render's free tier has no IPv6 outbound, so a direct URL fails there
with a DNS or connection error that looks like the database is down. Both pooler
hosts are IPv4.

Two more things that catch people:

- The pooler username is **`postgres.<project-ref>`**, not `postgres`.
- Alembic needs the **session** pooler. Transaction mode hands you a different
  backend per statement, which breaks DDL and advisory locks.

The driver prefix must be `postgresql+asyncpg://`, not `postgresql://`.

---

## 1. Supabase

Already done for this project (`nphbfmslcgktuzkcwqnm`, ap-south-1). The schema is
migrated and the default categories seed themselves on first API boot.

To verify or re-run:

```bash
cd backend
alembic upgrade head     # uses DATABASE_URL_MIGRATIONS from backend/.env
```

**Rotate the database password** before this is anything but a toy — the current
one has been pasted into a chat. Dashboard → Settings → Database → Reset
password, then update it in `backend/.env` and in Render's environment.

---

## 2. Render (backend)

New → Blueprint → connect `Mk6321/Expense_Tracker` → it picks up `render.yaml`.

Set these four secrets when prompted (the rest come from the blueprint, and
`JWT_SECRET` is generated for you):

| Key                       | Value                                                                 |
| ------------------------- | --------------------------------------------------------------------- |
| `DATABASE_URL`            | transaction pooler, port **6543**, prefix `postgresql+asyncpg://`      |
| `DATABASE_URL_MIGRATIONS` | session pooler, port **5432**, prefix `postgresql+asyncpg://`          |
| `CORS_ORIGINS`            | your Vercel URL — fill in after step 3, then redeploy                  |
| `PYTHON_VERSION`          | `3.11.9` (already in the blueprint)                                    |

The build command runs `alembic upgrade head`, so migrations apply on every
deploy.

Check `https://<your-service>.onrender.com/health` returns
`{"success":true,"data":{"status":"ok"}}`.

**Free tier sleeps** after ~15 minutes idle and takes 30–50s to wake. The
frontend says so explicitly on a slow first load rather than spinning silently.

---

## 3. Vercel (frontend)

Add New → Project → import the same repo. `vercel.json` at the root sets the
build, so leave the framework preset alone.

One environment variable:

```
VITE_API_BASE_URL = https://<your-service>.onrender.com
```

No trailing slash — the axios client appends `/api/v1` itself.

Deploy, then **go back to Render** and set `CORS_ORIGINS` to your Vercel URL
(e.g. `https://expense-tracker-mk6321.vercel.app`) and redeploy. Include the
preview domain too if you want preview builds to work:

```
https://expense-tracker.vercel.app,https://expense-tracker-git-main-mk6321.vercel.app
```

---

## 4. Check it end to end

1. Open the Vercel URL, register an account. First request may take ~40s while
   Render wakes; the app should say "Waking up the server…", not hang.
2. Create a group, generate an invite code.
3. Register a second account in a private window, join with the code.
4. Add a ₹100 expense split equally three ways → splits must read
   33.34 / 33.33 / 33.33 and the balances must sum to exactly zero.
5. Record a settlement and confirm the balance moves the right way.

If registration succeeds but nothing else loads, `CORS_ORIGINS` is wrong.
If everything 500s, the `DATABASE_URL` is almost certainly the direct one.

---

## Cross-origin cookies

Vercel and Render are different domains, so the refresh token cookie needs
`SameSite=None; Secure` (set via `COOKIE_SECURE=true`, `COOKIE_SAMESITE=none`)
and CORS needs `allow_credentials=True` with an explicit origin list. `*` is not
allowed with credentials and will fail silently in the browser.
