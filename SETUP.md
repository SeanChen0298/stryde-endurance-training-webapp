# Stryde — Setup Checklist

Work through this in order. Each section must be complete before the next.

---

## Prerequisites (one-time installs on your machine)

- [ ] **Python 3.11+** — `python --version` to check
- [ ] **Node.js 20+** — `node --version` to check
- [ ] **Git** — already installed if you cloned this repo

---

## Step 1 — Create free cloud accounts

Sign up for each service. All have permanent free tiers.

- [ ] **Neon** (database) — [console.neon.tech](https://console.neon.tech)
  - Create a project → choose region **AWS ap-southeast-1 (Singapore)**
  - Copy the connection string (format: `postgresql://user:pass@ep-xxx.ap-southeast-1.aws.neon.tech/neondb`)

- [ ] **Upstash** (Redis cache) — [console.upstash.com](https://console.upstash.com)
  - Create a Redis database → choose region **ap-southeast-1**
  - Copy the **REST URL** or **Redis URL** (format: `rediss://default:xxx@xxx.upstash.io:6379`)

- [ ] **Strava API app** — [strava.com/settings/api](https://www.strava.com/settings/api)
  - Create an app → set "Authorization Callback Domain" to `localhost` for now
  - Copy **Client ID** and **Client Secret**

- [ ] **Google Gemini API key** — [aistudio.google.com](https://aistudio.google.com)
  - Click "Get API key" → Create API key
  - This is **your personal key** — you will add it inside the app after setup, not in `.env`

- [ ] **Garmin Developer** (optional — can skip for now)
  - Apply at [developer.garmin.com](https://developer.garmin.com/gc-developer-program/) — approval takes ~2 business days
  - The app runs fine without this (Strava-only mode)

---

## Step 2 — Configure environment

```bash
# From repo root
cp .env.example backend/.env
```

Open `backend/.env` and fill in:

```bash
# From Neon — add ?sslmode=require at the end
DATABASE_URL=postgresql+asyncpg://user:pass@ep-xxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require

# From Upstash
REDIS_URL=rediss://default:xxx@xxx.upstash.io:6379

# Generate these two secrets — run each command once, copy the output
JWT_SECRET=          # python -c "import secrets; print(secrets.token_hex(32))"
GEMINI_ENCRYPTION_KEY=   # python -c "import secrets; print(secrets.token_hex(32))"

# From Strava
STRAVA_CLIENT_ID=
STRAVA_CLIENT_SECRET=
```

---

## Step 3 — Backend setup

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate it
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations (creates all tables on Neon)
alembic upgrade head

# Seed the athlete user
python ../scripts/seed.py
# → Prints the created email + a temporary password

# Start the dev server
uvicorn main:app --reload
# → API running at http://localhost:8000
# → Docs at http://localhost:8000/docs
```

- [ ] `pip install` completes with no errors
- [ ] `alembic upgrade head` shows `Running upgrade -> 001`
- [ ] `scripts/seed.py` prints `Created athlete: ...`
- [ ] `http://localhost:8000/health` returns `{"status": "ok"}`

---

## Step 4 — Frontend setup

```bash
cd frontend

# Install dependencies
npm install

# Create local env file
cp .env.local.example .env.local
# No edits needed — defaults to http://localhost:8000

# Start the dev server
npm run dev
# → App running at http://localhost:3000
```

- [ ] `npm install` completes with no errors
- [ ] `http://localhost:3000` loads the login page

---

## Step 5 — First login

1. Open [http://localhost:3000](http://localhost:3000)
2. Log in with the credentials printed by `seed.py` (default: `faiz@example.my` / `changeme123`)
3. You'll land on the Connect page → click **Connect Strava**
4. Authorise on Strava → redirected back → backfill starts in background
5. Go to **Settings → AI Configuration** → paste your Gemini API key → Save
6. Dashboard will show your Strava activities and (once AI is connected) daily brief

- [ ] Login works
- [ ] Strava OAuth completes and activities appear in dashboard
- [ ] Gemini key saves and shows "Connected"

---

## Step 6 — Strava webhook (optional for dev, required for production)

For real-time activity sync (rather than manual backfill), Strava needs to call a public URL.

**For local dev** use [ngrok](https://ngrok.com):
```bash
ngrok http 8000
# Gives you: https://abc123.ngrok.io
```

Then add to `backend/.env`:
```
STRAVA_WEBHOOK_CALLBACK_URL=https://abc123.ngrok.io/auth/webhooks/strava
```

Register the subscription (one-time):
```bash
curl -X POST https://www.strava.com/api/v3/push_subscriptions \
  -F client_id=YOUR_CLIENT_ID \
  -F client_secret=YOUR_CLIENT_SECRET \
  -F callback_url=https://abc123.ngrok.io/auth/webhooks/strava \
  -F verify_token=STRAVA_WEBHOOK_VERIFY_TOKEN
```

---

## Production hosting

See the "Production Deployment" section below.

---

---

# Production Deployment

## Backend → Vercel (serverless Python, free Hobby plan)

The backend is a second Vercel project next to the frontend. `backend/vercel.json`
routes every request to `backend/api/index.py`, which loads the FastAPI app.
It also pins the function to `sin1` (Singapore), next to Neon and Upstash —
Vercel's default is US East, which adds ~1 s per database connection.

Forgot the login password? `cd backend && .venv/Scripts/python ../scripts/reset_password.py`

1. [vercel.com](https://vercel.com) → **Add New → Project** → import this repo again
2. Name it e.g. `stryde-backend`, set **Root Directory** to `backend`, Framework Preset **Other**
3. Add environment variables (values from `backend/.env`):
   `DATABASE_URL`, `REDIS_URL` (must start with `rediss://`), `JWT_SECRET`,
   `GEMINI_ENCRYPTION_KEY`, `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`,
   `FRONTEND_URL` and `ALLOWED_ORIGINS` (the frontend's Vercel URL), and
   `CRON_SECRET` (generate: `python -c "import secrets; print(secrets.token_hex(32))"`)
4. Deploy → check `https://<backend>.vercel.app/health` returns `{"status":"ok"}`
5. Run migrations from your machine whenever a new one lands — serverless has no start step:
   ```bash
   cd backend && alembic upgrade head
   ```

How serverless changes behaviour (Vercel sets `VERCEL=1`, see `config.py`):

- No connection pool (`NullPool`); Neon's pooler handles pooling
- Work that used to run after the response (Garmin backfill, plan generation)
  runs inline, so those requests take longer — see `utils/background.py`
- A Garmin backfill stops after ~4 min (newest days first); press sync again for the rest
- No APScheduler. `.github/workflows/daily-jobs.yml` calls `POST /cron/daily`
  at 06:00 MYT. Add two repo secrets (GitHub → Settings → Secrets and variables → Actions):
  - `BACKEND_URL` → the backend's Vercel URL
  - `CRON_SECRET` → same value as in Vercel

  Test it once from GitHub → Actions → daily-jobs → **Run workflow**.

### After deploying backend

Run the seed script against production (one-time):
```bash
# Point to your production DATABASE_URL temporarily
DATABASE_URL=postgresql+asyncpg://... python scripts/seed.py
```

---

## Frontend → Vercel

1. Go to [vercel.com](https://vercel.com) → New Project → Import from GitHub
2. Set **Root Directory** to `frontend`
3. Framework preset auto-detects Next.js
4. Add environment variable:
   ```
   NEXT_PUBLIC_API_URL=https://your-backend.vercel.app
   ```
5. Deploy — Vercel gives you `https://stryde.vercel.app` (or custom domain)

---

## Production checklist

- [ ] Backend deployed and `https://your-backend.vercel.app/health` returns `{"status":"ok"}`
- [ ] `STRAVA_WEBHOOK_CALLBACK_URL` set to the production backend URL
- [ ] Frontend deployed and login page loads from Vercel URL
- [ ] CORS in `backend/main.py` updated to include the Vercel URL:
  ```python
  allow_origins=["https://stryde.vercel.app"]
  ```
- [ ] Strava webhook re-registered with production callback URL
- [ ] Set cookie `secure=True` in `backend/routers/auth.py` (line: `secure=False` → `secure=True`)
- [ ] Seed production DB with athlete user
- [ ] Log into production app and connect Strava

---

## Summary: where everything runs

| Component | Dev | Production |
|---|---|---|
| Backend | `localhost:8000` | Vercel serverless (free) |
| Frontend | `localhost:3000` | Vercel (free) |
| Database | Neon cloud (Singapore) | Same Neon instance |
| Redis | Upstash cloud | Same Upstash instance |
| Webhook tunnel | ngrok (temp) | Direct production URL |
