# Stryde — Claude Code Guide

> Read this file before generating any code. It supersedes the spec for execution decisions.

---

## Project at a glance

Personal endurance training platform for a single athlete (Muhammad Faizal, Penang, Malaysia).
Consolidates Strava + Garmin data with Google Gemini AI coaching. **$0/month to run.**

| Layer | Technology | Notes |
|---|---|---|
| Backend | FastAPI + Python 3.11 | `backend/` — `uvicorn main:app --reload` |
| Frontend | Next.js 14 App Router + TypeScript | `frontend/` — `npm run dev` |
| Database | Neon PostgreSQL (pgvector + TimescaleDB) | AWS ap-southeast-1 (Singapore) |
| Cache | Upstash Redis | Rate limiting + daily quota counters |
| AI | Google Gemini API | **User provides their own free key** — never in `.env` |
| Hosting | Railway/Render (backend) + Vercel (frontend) | All free tier |

---

## Repo layout

```
/
├── backend/
│   ├── main.py               ← FastAPI app entry point
│   ├── config.py             ← All settings via pydantic-settings (reads backend/.env)
│   ├── database.py           ← Async SQLAlchemy engine
│   ├── dependencies.py       ← FastAPI Depends() helpers (DB, Redis, current_athlete)
│   ├── models/               ← SQLAlchemy ORM models
│   ├── routers/              ← One router per feature domain
│   ├── services/             ← External API clients + business logic
│   ├── utils/                ← Pure helpers (pace, hrv, jwt, encryption)
│   ├── prompts/              ← Gemini prompt builders (Phase 2+)
│   ├── migrations/           ← Alembic (run: alembic upgrade head)
│   └── tests/                ← pytest tests for the 4 high-risk areas
├── frontend/
│   └── src/
│       ├── app/              ← Next.js App Router pages
│       ├── components/       ← Shared React components
│       ├── lib/              ← api.ts, theme.ts, queryClient.ts
│       └── styles/globals.css ← ALL design tokens live here
├── scripts/
│   └── seed.py               ← Run once to create the athlete user
├── .env.example              ← Template — copy to backend/.env and fill in
└── ENDURANCE_PLATFORM_SPEC.md ← Full product spec (reference only)
```

---

## Critical rules — never violate these

### 1. Strava AI compliance
Raw Strava API responses are written to `activities.raw_metadata` (JSONB) **and immediately discarded**.
The AI layer (`prompts/`, `services/ai_service.py`) reads **only** from the normalised `activities` table.
Never pass `raw_metadata` or anything from `strava_client.py` to a Gemini prompt.
Add this comment at every compliance boundary:
```python
# Uses internal schema only — not Strava API data
```

### 2. Gemini key — never in .env
Each user provides their own free key via the Settings page.
It is AES-256-GCM encrypted (`utils/encryption.py`) before storage.
`config.py` has `GEMINI_ENCRYPTION_KEY` (master AES key) but **not** `GEMINI_API_KEY`.
Always decrypt with `utils/encryption.decrypt_api_key(athlete.gemini_api_key_encrypted)` at call time.

### 3. Garmin is optional
`GARMIN_CLIENT_ID` is empty during Phase 1. Code must degrade gracefully — never crash if Garmin creds are absent.
Pattern: `if not settings.GARMIN_CLIENT_ID: return None / skip silently`.

### 4. Single-user app
No registration. One athlete seeded via `scripts/seed.py`. JWT in httpOnly cookie.
All protected routes use `Depends(get_current_athlete)` from `dependencies.py`.

### 5. Design system — CSS custom properties only
All colour/typography tokens are CSS `var(--token)` from `frontend/src/styles/globals.css`.
**Never hardcode hex values in React components.**
Use the design tokens exactly as defined in `globals.css`.

---

## Build phase status

| Phase | Status | Key features |
|---|---|---|
| **Phase 1** | ✅ Built | DB schema, Strava/Garmin sync, dashboard, activities, settings |
| **Phase 2** | ⬜ Next | Readiness score, Gemini daily brief, health dashboard |
| **Phase 3** | ⬜ Planned | Training plan generation, adaptive revision, calendar |
| **Phase 4** | ⬜ Planned | PMC chart, race predictor, segment analysis |

---

## Phase 2 — what to build next

1. `services/readiness_service.py` — compute daily readiness score from HRV/sleep/load
2. `services/gemini_client.py` + `services/rate_limiter.py` — from spec (already spec'd, not coded)
3. `services/ai_service.py` — `generate_daily_brief()`
4. `prompts/daily_brief.py` — prompt builder
5. `routers/health.py` — `/health` (history), `/health/{date}` (day detail)
6. Scheduler: add morning brief job at 06:05 MYT
7. Frontend: `/dashboard/health` and `/dashboard/health/[date]` pages
8. Upgrade `/dashboard` page.tsx to Phase 2 state (readiness ring + AI brief)

---

## Execution order (from spec)

Always follow this order within a phase. Do not skip ahead:
1. Backend models (if new tables needed)
2. Alembic migration
3. Service layer
4. Router
5. Frontend page

---

## Key patterns

### FastAPI router pattern
```python
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from dependencies import get_current_athlete
from models.athlete import Athlete

router = APIRouter()

@router.get("/example")
async def example(
    athlete: Annotated[Athlete, Depends(get_current_athlete)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ...
```

### Error response shape
```python
# Raise HTTPException — never return raw errors
raise HTTPException(status_code=404, detail="Not found")
# For AI errors: raise GeminiDailyLimitReached — handled globally in main.py
```

### Frontend data fetching
```typescript
// Always use React Query — never raw fetch in components
const { data, isLoading } = useQuery({
  queryKey: ["dashboard"],
  queryFn: api.dashboard,
})
```

### Theme-safe CSS
```typescript
// Good — uses design token
<div style={{ color: "var(--accent)" }}>

// Bad — hardcoded hex
<div style={{ color: "#F97316" }}>
```

---

## Testing — only 4 areas

Per spec, only test these high-risk areas:

1. **Rate limiter** — token bucket logic (Phase 2, when `rate_limiter.py` is built)
2. **Data normalisation** — `tests/test_normalisation.py` (exists)
3. **Prompt builders** — snapshot test generated prompts (Phase 2+)
4. **Encryption round-trip** — `tests/test_encryption.py` (exists)

Run: `cd backend && pytest tests/ -v`

---

## Environment variables

All in `backend/.env` (copy from `.env.example`). Required for startup:
- `DATABASE_URL` — Neon connection string (`postgresql+asyncpg://...`)
- `REDIS_URL` — Upstash Redis (`rediss://...`)
- `GEMINI_ENCRYPTION_KEY` — 32-byte hex, generate once
- `JWT_SECRET` — random hex, generate once
- `STRAVA_CLIENT_ID` + `STRAVA_CLIENT_SECRET`

Optional (app works without them):
- `GARMIN_CLIENT_ID` / `GARMIN_CLIENT_SECRET` — Garmin sync disabled if absent
- `GOOGLE_CALENDAR_*` — Phase 3 feature
- `STRAVA_WEBHOOK_CALLBACK_URL` — needed for real-time webhook (can use ngrok for dev)
