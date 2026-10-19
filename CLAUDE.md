# Stryde — Agent Guide

> Read this before any change. It overrides `ENDURANCE_PLATFORM_SPEC.md` wherever they disagree.
> The spec is background; this file and `ROADMAP.md` are the current truth.

## What Stryde is

A single-user training and recovery platform for one athlete (the repo owner, Kuala Lumpur,
timezone `Asia/Kuala_Lumpur`). It pulls runs and recovery data from Garmin, plans training around
them with Gemini, and shows the athlete their own data. Costs $0/month to run.

| Layer | Technology | Where |
|---|---|---|
| Backend | FastAPI, Python 3.11 | `backend/` — Railway |
| Frontend | Next.js 14 App Router, TypeScript, React Query | `frontend/` — Vercel |
| Database | Neon PostgreSQL | Alembic migrations in `backend/migrations/` |
| Cache | Upstash Redis | rate limits, quota counters |
| AI in the app | Google Gemini, user-provided key | never in `.env` |
| Jobs | APScheduler, `backend/services/scheduler.py` | runs inside the backend |

## Data sources

- **Garmin Connect is the only data source**, for both activities and health
  (HRV, sleep, resting HR, body battery). Access is through the unofficial
  `python-garminconnect` library signing in to the owner's own account.
- **Strava is switched off and must stay off.** Strava's API Policy (June 2026) forbids
  using Strava data in any AI feature (§5.3, including putting it in a prompt), forbids search
  indexes built from it (§5.5), and limits caching to 7 days (§6.2). Do not add Strava calls,
  do not read `source = 'strava'` rows in any AI path, and do not re-enable it.

## What's built

- Garmin health sync, health page, daily readiness score, Gemini morning brief
- Gemini-written training plans, calendar view, rule-based plan revision
  (`plan_service.check_revision_triggers`)
- Activities list and detail pages
- Settings: Gemini key, Garmin sign-in, manual sync

What's next lives in `ROADMAP.md`. Do not start work that isn't in an issue.

## Commands

```bash
# backend
cd backend && pip install -r requirements.txt pytest
pytest -q                        # must pass before any PR
uvicorn main:app --reload        # local server, needs backend/.env

# frontend
cd frontend && npm ci
npm run build                    # must pass before any PR
```

CI (`.github/workflows/ci.yml`) runs both on every pull request. `main` is protected:
changes land only through a pull request with green `backend` and `frontend` checks.

Tests import modules without a real database: `tests/conftest.py` sets dummy settings.
Never call real Garmin, Gemini, GitHub or weather APIs in tests — use fakes.

## Rules — never break these

1. **No Strava.** See "Data sources" above.
2. **No secrets or personal data in the repo.** No tokens, cookies, keys, `.env` files or data
   exports. The Gemini key and Garmin tokens are stored AES-256-GCM encrypted
   (`utils/encryption.py`) and decrypted only at call time.
3. **Every external source is optional.** If Garmin or Gemini isn't connected, the app still
   starts and the feature degrades quietly. Never crash on missing credentials.
4. **Garmin politely.** One signed-in client per sync run, never a fresh sign-in per request.
   Keep daily syncs small; full backfills only on connect or manual sync.
5. **Single user.** No registration. Protected routes use `Depends(get_current_athlete)`.
6. **Design tokens only.** Colours and type come from CSS variables in
   `frontend/src/styles/globals.css`. No hex values in components.
7. **AI drafts, rules decide.** Anything that changes the plan is decided by plain, tested
   code. Gemini writes wording or a first draft that rules then check.
8. **Stay inside your issue.** Touch only the files the issue names. If the issue is unclear or
   contradicts this file, stop and say so in the issue instead of guessing.
9. **Never edit the pipeline's own files:** `.github/`, `.claude/`, `CLAUDE.md`, `ROADMAP.md`.
   Those belong to the owner.

## How to build a change

Order inside a feature: model → Alembic migration → service → router → frontend page.

- Backend router pattern: `APIRouter`, `Annotated[...]` dependencies, raise `HTTPException`.
- Frontend data: React Query only, through `frontend/src/lib/api.ts`. No raw `fetch` in components.
- A schema change is its own migration with a working downgrade.

## Testing

Every PR adds or updates tests for what it changes. Priorities:

- Rule logic: readiness, plan revision triggers, plan validation
- Data normalisation for each Garmin payload (activities, sleep, HRV, stats)
- Prompt builders: snapshot the generated prompt
- Encryption round trip
- API endpoints: status codes and response shape with a faked database layer

## Definition of done

- `pytest` and `npm run build` pass (CI shows both green)
- The issue's own "done means" check is met and shown in the PR description
- No secrets, no edits outside the issue's files
- The PR description says what changed, how it was checked, and anything left open
