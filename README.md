# Stryde — Endurance Training Platform

A personal full-stack web platform consolidating Garmin + Strava data with Google Gemini AI coaching.

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.11+) |
| Frontend | Next.js 14 (TypeScript, App Router) |
| Database | Neon PostgreSQL (pgvector + TimescaleDB) |
| Cache | Upstash Redis |
| AI | Google Gemini API (user-provided key) |
| Hosting | Railway/Render (backend) + Vercel (frontend) |

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+
- A [Neon](https://neon.tech) database
- An [Upstash Redis](https://upstash.com) instance
- A [Strava API app](https://www.strava.com/settings/api)

### 1. Clone and configure

```bash
git clone <repo>
cd stryde-endurance-training
cp .env.example backend/.env
# Edit backend/.env with your credentials
```

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Seed the single athlete user
python ../scripts/seed.py

# Start dev server
uvicorn main:app --reload
# → http://localhost:8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

## Build Phases

- **Phase 1** — Data foundation: Strava/Garmin sync, dashboard, activities
- **Phase 2** — Health analyst: readiness scores, daily AI brief
- **Phase 3** — Training planner: AI plan generation, calendar, adaptive revision
- **Phase 4** — Advanced: PMC chart, race predictor, segment analysis

## Architecture Notes

- Single-user app — no registration flow, one seeded athlete
- JWT in `httpOnly` cookie
- User provides their own free Gemini API key (never stored in `.env`)
- Strava data is normalised into internal schema before reaching the AI layer (compliance)
- Garmin credentials optional — app runs in Strava-only mode if not configured
