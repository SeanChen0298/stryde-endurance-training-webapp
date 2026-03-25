# Endurance Training Platform — Project Specification
> Claude Code consumption document · v1.4 — User-provided Gemini API key; design system added

---

## Overview

A full-stack web platform for endurance athletes that consolidates Garmin Connect and Strava data into a personalised dashboard, and pairs it with Google Gemini AI for adaptive training coaching, health analysis, and race intelligence.

**Target user**: Solo endurance trainer based in Malaysia (Penang), primarily running (half marathon, marathon). Uses Garmin device + Strava.

**AI provider**: Google Gemini API — provided by the user. Each user supplies their own API key obtained free from Google AI Studio (aistudio.google.com). The key is stored encrypted in the database per user, never in `.env`. This means each user operates under their own quota — no shared rate-limit pool.

**Hardware requirement**: None. The entire stack runs on managed cloud services with generous free tiers. No local server, VPS, or strong hardware is needed — a regular laptop is sufficient for development only.

---

## Claude Code — Execution Guide

> **Read this section first before generating any code.**

This section gives Claude Code everything it needs to begin executing without asking clarifying questions.

### Execution order

Always follow this phase order. Do not jump ahead. Each phase produces working, runnable code before the next begins.

1. **Repo and tooling setup** — monorepo scaffold, dependency files, `.env.example`, `.gitignore`
2. **Database** — Neon connection, run schema migrations via Alembic, verify extensions
3. **Data ingestion** — Strava + Garmin OAuth, sync pipeline, webhook registration
4. **Backend features** — one router + service pair at a time, in phase order from the Build Phases section
5. **Frontend** — Next.js scaffold, then one dashboard page at a time

### Repository structure

```
/                          # monorepo root
├── backend/               # FastAPI Python app
├── frontend/              # Next.js app
├── scripts/               # one-off setup and seed scripts
├── .env.example           # committed — variable names, no values
├── .gitignore
└── README.md
```

### Backend bootstrap

```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload       # local dev server at localhost:8000
```

**`requirements.txt`** — generate this file with exactly these packages:
```
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
alembic==1.14.0
httpx==0.27.2
redis[asyncio]==5.2.0
tenacity==9.0.0
apscheduler==3.10.4
sentence-transformers==3.3.1
pandas==2.2.3
numpy==1.26.4
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.12
pydantic-settings==2.6.1
python-dotenv==1.0.1
cryptography==43.0.3
```

### Frontend bootstrap

```bash
cd frontend
npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir --import-alias "@/*"
npm install recharts lucide-react date-fns
npm run dev                     # local dev at localhost:3000
```

### Database migrations (Alembic)

```bash
cd backend
alembic init migrations
# Edit migrations/env.py to use async SQLAlchemy and load DATABASE_URL from .env
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

Always use Alembic for schema changes — never edit the DB directly in production. Migration files must be committed to the repo.

### Authentication strategy

This is a **single-user personal app**. Keep auth simple:

- No registration flow needed
- One hardcoded admin user seeded to the `athletes` table on first run
- Session via **JWT** stored in an `httpOnly` cookie
- The login page accepts email + password, issues a JWT, all API routes check the token
- Strava and Garmin use **OAuth 2.0** — after login, the user connects each service via the `/auth/strava` and `/auth/garmin` routes which store tokens in `oauth_tokens`

```python
# Single user seed (run once via scripts/seed.py)
INSERT INTO athletes (email, name, timezone, goal_race_type)
VALUES ('your@email.com', 'Your Name', 'Asia/Kuala_Lumpur', 'marathon');
```

```python
# JWT dependency — apply to all protected routes
async def get_current_athlete(token: str = Depends(oauth2_scheme), db = Depends(get_db)):
    payload = decode_jwt(token)
    athlete = await db.get(Athlete, payload["sub"])
    if not athlete:
        raise HTTPException(status_code=401)
    return athlete
```

### Error handling conventions

All FastAPI routers must follow this pattern — no bare `try/except` that swallows errors silently:

```python
# Standard API error response shape
class APIError(BaseModel):
    error: str
    detail: str | None = None
    code: str | None = None

# Use FastAPI exception handlers, not inline try/except in routes
@app.exception_handler(GeminiDailyLimitReached)
async def gemini_limit_handler(request, exc):
    return JSONResponse(status_code=503, content={"error": "AI quota reached", "code": "AI_QUOTA"})

@app.exception_handler(httpx.HTTPStatusError)
async def external_api_handler(request, exc):
    return JSONResponse(status_code=502, content={"error": "External API error", "detail": str(exc)})
```

Frontend must handle these codes explicitly — show a user-friendly banner, never a raw error.

### Environment variable loading

```python
# backend/config.py — single source of truth for all settings
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    # NOTE: No GEMINI_API_KEY here — each user provides their own key via Settings page.
    # The key is stored encrypted in the athletes table.
    GEMINI_ENCRYPTION_KEY: str   # 32-byte AES key for encrypting user Gemini keys — generate once: secrets.token_hex(32)
    GEMINI_PRIMARY_MODEL: str = "gemini-2.5-flash"
    GEMINI_FAST_MODEL: str = "gemini-2.5-flash-lite"
    STRAVA_CLIENT_ID: str
    STRAVA_CLIENT_SECRET: str
    GARMIN_CLIENT_ID: str = ""       # optional during prototyping
    GARMIN_CLIENT_SECRET: str = ""
    GOOGLE_CALENDAR_CLIENT_ID: str = ""
    GOOGLE_CALENDAR_CLIENT_SECRET: str = ""
    JWT_SECRET: str
    JWT_EXPIRE_HOURS: int = 24 * 7   # 7 days
    ATHLETE_TIMEZONE: str = "Asia/Kuala_Lumpur"

    class Config:
        env_file = ".env"

settings = Settings()
```

### Dependency injection pattern

Use FastAPI's `Depends` for all shared resources — never instantiate clients inside route handlers:

```python
# backend/dependencies.py
from functools import lru_cache

@lru_cache
def get_settings() -> Settings:
    return Settings()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def get_redis():
    return await aioredis.from_url(settings.REDIS_URL)

async def get_gemini_client():
    redis = await get_redis()
    rate_limiter = GeminiRateLimiter(redis)
    return GeminiClient(rate_limiter)

async def get_ai_service(gemini = Depends(get_gemini_client)):
    return AIService(gemini)
```

### Frontend API communication

All backend calls from Next.js go through a single typed client — no raw `fetch` calls scattered in components:

```typescript
// frontend/src/lib/api.ts
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    credentials: "include",   // send httpOnly JWT cookie
    headers: { "Content-Type": "application/json", ...options?.headers },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new APIError(res.status, err.error ?? "Unknown error", err.code)
  }
  return res.json()
}

export const api = {
  dashboard:   () => apiFetch<DashboardData>("/dashboard"),
  activities:  () => apiFetch<Activity[]>("/activities"),
  plan:        () => apiFetch<TrainingPlan>("/plans/active"),
  health:      (date: string) => apiFetch<HealthMetrics>(`/health/${date}`),
  // ... extend per feature
}
```

### What to do when an API credential is missing

During Phase 1 and 2 development, Garmin API approval may still be pending. The code must handle missing credentials gracefully:

- If `GARMIN_CLIENT_ID` is empty, skip all Garmin sync jobs silently — do not crash the app
- Log a single warning at startup: `"Garmin credentials not configured — sync disabled"`
- All Garmin-dependent dashboard widgets should render with a "Connect Garmin" prompt instead of an error
- Strava-only mode must be fully functional as a fallback

### Testing approach

Write tests for the four highest-risk areas only — do not write tests for everything:

1. **Rate limiter** — unit test the token bucket logic per user bucket
2. **Data normalisation** — test that Strava/Garmin payloads map correctly to the internal schema
3. **Prompt builders** — snapshot test the generated prompts to catch accidental regressions
4. **Encryption round-trip** — verify `decrypt_api_key(encrypt_api_key(key)) == key` and that the ciphertext is never equal to the plaintext

```bash
cd backend
pip install pytest pytest-asyncio
pytest tests/ -v
```

---

## Design System

> **Claude Code must follow this section precisely when generating all frontend HTML mockups and React components. Do not deviate from these tokens, patterns, or animation specs.**

### Design philosophy

- **Whitespace over borders** — components are separated by spacing and typographic contrast, not lines or dividers
- **Data-first** — every pixel serves legibility of numbers and trends; decoration is removed unless it carries meaning
- **Mobile-first, desktop-enhanced** — base layout targets 390px (iPhone 14). Desktop breakpoints (`md:`, `lg:`) add columns and richer chart views on top
- **One accent colour** — everything is black, white, and four grays. The accent appears only on active states, progress fills, primary CTAs, and key metric highlights
- **Calm animations** — motion confirms actions and reveals data; it never draws attention to itself

---

### Colour tokens

Define these as CSS custom properties on `:root`. Never hardcode hex values in components.

```css
:root {
  /* Accent — user-selectable, default Ember */
  --accent:         #F97316;
  --accent-light:   #FED7AA;   /* tints: accent at 20% opacity on white */
  --accent-dim:     #C2410C;   /* darker shade for hover/active states */

  /* Grayscale */
  --gray-0:   #FFFFFF;   /* page background */
  --gray-50:  #F9F9F9;   /* card background */
  --gray-100: #F0F0F0;   /* subtle surface, skeleton loader */
  --gray-200: #E0E0E0;   /* dividers (used sparingly) */
  --gray-400: #9E9E9E;   /* secondary labels, metadata */
  --gray-600: #5E5E5E;   /* body text, descriptions */
  --gray-900: #111111;   /* primary text, headings, values */

  /* Semantic (used only for status — not decoration) */
  --status-green:  #22C55E;   /* good recovery, on-target */
  --status-amber:  #F59E0B;   /* caution, slightly below baseline */
  --status-red:    #EF4444;   /* poor recovery, alert */
}
```

**User theme presets** — stored in `localStorage` as `--accent` hex value only. Everything else stays constant.

| Name | Hex | Feel |
|---|---|---|
| Ember (default) | `#F97316` | Strava-adjacent, energetic |
| Cobalt | `#3B82F6` | Clean, Garmin-ish |
| Jade | `#10B981` | Health, recovery |
| Violet | `#8B5CF6` | Premium, calm |
| Crimson | `#EF4444` | Intense, racing |

---

### Typography scale

```css
/* All weights: 400 (regular) and 600 (semibold) only — no 700 */

--text-xs:   11px;   /* metadata labels, timestamps — uppercase + tracking */
--text-sm:   13px;   /* secondary body, card descriptions */
--text-base: 15px;   /* primary body text */
--text-lg:   17px;   /* card section headings */
--text-xl:   22px;   /* module page headings */
--text-2xl:  28px;   /* primary metric values (e.g. 47 km, 52ms HRV) */
--text-3xl:  36px;   /* hero metric (readiness score on overview) */
```

Usage rules:
- Metric **values**: `--text-2xl`, weight 600, `--gray-900`
- Metric **labels**: `--text-xs`, weight 400, `--gray-400`, uppercase, `letter-spacing: 0.06em`
- Card **titles**: `--text-sm`, weight 600, `--gray-900`
- Body **descriptions**: `--text-sm`, weight 400, `--gray-600`
- **Delta indicators** (↑ 12%, ↓ 8%): `--text-xs`, coloured with semantic tokens

---

### Spacing and layout

```css
/* Content container — centered, max-width constrained on desktop */
.container {
  width: 100%;
  max-width: 480px;       /* mobile: full width */
  margin: 0 auto;
  padding: 0 16px;
}

@media (min-width: 768px) {
  .container {
    max-width: 900px;     /* desktop: wider but not full-screen */
    padding: 0 32px;
  }
}
```

Card spacing rules:
- Card internal padding: `16px` mobile, `20px` desktop
- Gap between cards: `12px`
- Section gap (between card groups): `24px`
- Card `border-radius`: `16px`
- Card `background`: `var(--gray-50)`
- Card `box-shadow`: none — background contrast + radius is sufficient

---

### Overview hub — card grid

**Mobile (single column, mixed widths):**
```
[Full width]  Readiness header card
[Half] [Half] Sleep | This week
[Half] [Half] HRV   | Next run
[Full width]  Training load sparkline
[Full width]  AI daily brief
```

**Desktop (two-column grid, full-width cards span both columns):**
```css
.card-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.card-full  { grid-column: 1 / -1; }  /* spans both columns */
.card-half  { grid-column: span 1; }
```

Full-width cards: Readiness header, Training load, AI brief, Training calendar strip
Half-width cards: Sleep, Weekly mileage, HRV, Next run, Segment highlight, Gear alert

---

### Navigation

**Bottom tab bar (mobile + desktop):**

```
[Overview] [Training] [Health] [Analysis] [Settings]
   icon       icon      icon      icon       icon
   label      label     label     label      label
```

```css
.tab-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 64px;
  background: var(--gray-0);
  display: flex;
  justify-content: space-around;
  align-items: center;
  /* No border-top — use subtle box-shadow instead */
  box-shadow: 0 -1px 0 var(--gray-100);
  padding-bottom: env(safe-area-inset-bottom);  /* iPhone notch */
  z-index: 100;
}

.tab-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  color: var(--gray-400);
  font-size: var(--text-xs);
}

.tab-item.active {
  color: var(--accent);
}
```

On desktop (`md:` and above): the tab bar moves to a **top navigation bar** at 56px height with the same 5 items as horizontal links, right-aligned. The content area gets `padding-top: 56px` instead of `padding-bottom: 64px`.

---

### Page transitions

All navigation uses **full page transitions** (your chosen preference). Implement with Framer Motion:

```typescript
// Every page component wraps its content in this
import { motion } from "framer-motion"

const pageVariants = {
  initial:  { opacity: 0, y: 16 },
  animate:  { opacity: 1, y: 0, transition: { duration: 0.22, ease: "easeOut" } },
  exit:     { opacity: 0, y: -8, transition: { duration: 0.15 } },
}

export function PageWrapper({ children }: { children: React.ReactNode }) {
  return (
    <motion.div variants={pageVariants} initial="initial" animate="animate" exit="exit">
      {children}
    </motion.div>
  )
}
```

Add `<AnimatePresence mode="wait">` in the root layout wrapping `{children}`.

---

### Animation catalogue

Every animation used in the app is defined here. Claude Code must not invent animations outside this list.

| Element | Animation | Spec |
|---|---|---|
| Page enter | Fade up | `opacity 0→1`, `y 16→0`, `220ms easeOut` |
| Card tap | Scale feedback | `scale 1→0.97` on press, `1→1` on release, `100ms` |
| Metric count-up | Number increment | Count from 0 to value over `800ms` with `easeOut` on mount |
| Sparkline draw | SVG stroke | `stroke-dashoffset` animation, `600ms easeOut` on mount |
| Readiness ring | Arc draw | SVG `stroke-dashoffset`, `900ms easeOut` on mount |
| Skeleton loader | Shimmer | `background-position` shift, `1.4s linear infinite` |
| Tab switch | Indicator slide | Accent underline `translateX` to active tab, `200ms easeOut` |
| Progress bar fill | Width expand | `width 0→value%`, `700ms easeOut` on mount |
| AI brief reveal | Fade in lines | Each line fades in sequentially, `150ms` stagger |
| HRV dot pulse | Single pulse | `scale 1→1.4→1`, `opacity 1→0`, `600ms` once on mount |

All animations must respect `prefers-reduced-motion`:
```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

### Component patterns

**Metric card (half-width):**
```
┌─────────────────────┐
│  LABEL         delta │  ← xs uppercase gray-400 | xs accent/status
│                      │
│  Value               │  ← 2xl semibold gray-900
│  sub-label           │  ← xs gray-400
│  [sparkline]         │  ← optional, 32px tall
└─────────────────────┘
```

**Full-width summary card:**
```
┌─────────────────────────────────────┐
│  LABEL                    →  detail │  ← xs label | xs accent "See all"
│                                     │
│  Primary content / chart            │
│  Supporting line                    │  ← sm gray-600
└─────────────────────────────────────┘
```

**Readiness header card (full-width, hero):**
```
┌─────────────────────────────────────┐
│  Good morning           Tue 25 Mar  │  ← sm gray-400
│                                     │
│     [Ring]   78                     │  ← ring in accent, 3xl value
│              Ready to train         │  ← sm status-green
│                                     │
│  "HRV slightly suppressed…"         │  ← sm gray-600, AI one-liner
└─────────────────────────────────────┘
```

**Status delta indicator:**
```typescript
// Always rendered as: ↑ 12%  or  ↓ 8%
// Color: status-green for improvement, status-red for decline, gray-400 for neutral
function Delta({ value, positiveIsGood = true }: { value: number, positiveIsGood?: boolean }) {
  const improved = positiveIsGood ? value > 0 : value < 0
  const color = value === 0 ? "var(--gray-400)"
              : improved    ? "var(--status-green)"
                            : "var(--status-red)"
  return (
    <span style={{ color, fontSize: "var(--text-xs)" }}>
      {value > 0 ? "↑" : "↓"} {Math.abs(value)}%
    </span>
  )
}
```

Note: for HRV and resting HR, a negative delta is *good* (HRV up = good, HR down = good). Pass `positiveIsGood={false}` for resting HR.

---

### Client-side rendering strategy

```
Page shell        → server rendered (Next.js App Router, layout.tsx)
Navigation        → client component (tab state)
All data fetching → client components using React Query
Charts (Recharts) → client only, dynamic import with ssr: false
Animations (Framer Motion) → client only
Theme switcher    → client only, reads/writes localStorage
```

```typescript
// All data-fetching components follow this pattern
"use client"
import { useQuery } from "@tanstack/react-query"

export function WeeklyMileageCard() {
  const { data, isLoading } = useQuery({
    queryKey: ["weekly-mileage"],
    queryFn: () => api.dashboard.weeklyMileage(),
    staleTime: 5 * 60 * 1000,   // 5 min cache — no unnecessary refetches
  })

  if (isLoading) return <CardSkeleton />   // shimmer, not spinner

  return (
    <MetricCard
      label="THIS WEEK"
      value={`${data.km} km`}
      delta={data.deltaPercent}
    />
  )
}
```

Install: `npm install @tanstack/react-query framer-motion`

---

### Theme switcher implementation

```typescript
// frontend/src/lib/theme.ts
const THEMES = {
  ember:   { name: "Ember",   accent: "#F97316", accentLight: "#FED7AA", accentDim: "#C2410C" },
  cobalt:  { name: "Cobalt",  accent: "#3B82F6", accentLight: "#BFDBFE", accentDim: "#1D4ED8" },
  jade:    { name: "Jade",    accent: "#10B981", accentLight: "#A7F3D0", accentDim: "#047857" },
  violet:  { name: "Violet",  accent: "#8B5CF6", accentLight: "#DDD6FE", accentDim: "#6D28D9" },
  crimson: { name: "Crimson", accent: "#EF4444", accentLight: "#FECACA", accentDim: "#B91C1C" },
}

export function applyTheme(key: keyof typeof THEMES) {
  const t = THEMES[key]
  const root = document.documentElement
  root.style.setProperty("--accent",       t.accent)
  root.style.setProperty("--accent-light", t.accentLight)
  root.style.setProperty("--accent-dim",   t.accentDim)
  localStorage.setItem("theme", key)
}

export function loadSavedTheme() {
  const saved = localStorage.getItem("theme") as keyof typeof THEMES | null
  if (saved && THEMES[saved]) applyTheme(saved)
}
// Call loadSavedTheme() in the root layout useEffect
```

Theme swatches in Settings page — 5 circles, tap to apply, active swatch has `border: 2px solid var(--accent)`.

---

## Free Infrastructure Stack

All services below have a usable free tier for solo/personal use.

| Layer | Service | Free Tier Notes |
|---|---|---|
| Database | **Neon** (serverless PostgreSQL) | 0.5 GB storage, 100 CU-hours/month, supports pgvector + TimescaleDB extensions, no credit card, never expires |
| Vector / RAG | **pgvector** (Neon extension) | Free, built into Neon — `CREATE EXTENSION vector` |
| Time-series | **TimescaleDB** (Neon extension) | Free, built into Neon — `CREATE EXTENSION timescaledb` |
| Backend | **Railway** free tier or **Render** free tier | FastAPI app, auto-deploys from GitHub |
| Frontend | **Vercel** free tier | Next.js, unlimited personal projects |
| Background jobs | **APScheduler** (in-process) | No extra service needed at this scale |
| Cache | **Upstash Redis** free tier | 10,000 commands/day free |
| AI | **Google Gemini API** (user-provided key) | User supplies their own free key from aistudio.google.com — each user has their own quota, no shared limits |
| AI key storage | **Encrypted in DB** (per athlete) | AES-256 encrypted, stored in `athletes` table — never in `.env` or logs |
| AI rate limiting | **In-process token bucket** (per user) | Enforced per `athlete_id` to absorb bursts; protects against accidental hammering |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (local) | Runs locally via `sentence-transformers` Python lib — $0, no API call needed |
| Weather (global) | **Open-Meteo API** | Free, no key — temperature, humidity, apparent temp, wind (reliable for tropics) |
| Weather (local) | **MET Malaysia API** | Free, no key — rain warnings, local alerts from Malaysian Met Dept (data.gov.my) |
| Calendar export | **Google Calendar API** | Free for personal use |

> **Summary**: Entire stack is **$0/month**. The Gemini API key is free to obtain from Google AI Studio — no credit card required. Each user brings their own key so quota is never shared, and the app never holds a master API key.

---

## Database Hosting — No Hardware Required

**Everything runs on Neon's managed cloud.** You do not need a local database, a VPS, or any server hardware. Here is exactly what runs where:

| Component | Where it runs | Hardware you need |
|---|---|---|
| PostgreSQL database | Neon cloud (Singapore region recommended) | None |
| pgvector extension | Inside Neon — same instance | None |
| TimescaleDB extension | Inside Neon — same instance | None |
| FastAPI backend | Railway or Render cloud (auto-deploy from GitHub) | None |
| Next.js frontend | Vercel cloud (auto-deploy from GitHub) | None |
| Redis cache | Upstash cloud | None |
| Embeddings model | Your laptop during development only | A laptop (any modern one) |
| **Production runtime** | **100% cloud** | **None** |

### Neon specifics for Malaysia
- Choose **AWS ap-southeast-1 (Singapore)** as your Neon region — closest available to Penang, lowest latency
- Neon's serverless architecture scales to zero when idle and wakes in ~500ms — perfect for a personal app with low traffic
- The 0.5 GB free storage limit is plenty: a year of daily health metrics + activity data + embeddings for a solo athlete fits comfortably within ~100–200 MB
- Connection from Railway/Render backend to Neon uses a standard `DATABASE_URL` connection string — no firewall rules or network config needed

### Development workflow (no hardware needed)
```bash
# All you need on your laptop is:
# 1. Node.js (for Next.js)
# 2. Python 3.11+ (for FastAPI)
# 3. Git

# Connect directly to cloud Neon DB from local machine using psql or any GUI
psql $DATABASE_URL

# Or use Neon's built-in SQL editor at console.neon.tech — no local tools needed at all
```

You can even do the entire database setup (schema migrations, seeding) through Neon's web console without installing anything locally.

---

## External API Status

### Strava V3 API
- **Cost**: Free
- **Rate limits**: 200 requests / 15 min, 2,000 / day
- **Auth**: OAuth 2.0
- **Key data available**: Activities (runs), pace, HR zones, segments, gear, athlete stats, routes, kudos, splits
- **Critical caveat**: Strava's updated terms **prohibit using API data to train or prompt AI/ML models**. Architecture must normalise Strava data into your own internal schema before it touches the AI layer. The prompt context must reference your schema, not raw Strava API responses. This keeps you compliant and Strava swappable.
- **Webhook support**: Yes — use webhooks for real-time activity sync

### Garmin Connect Developer Program
- **Cost**: Free for approved developers; Health API commercial use requires license fee (not applicable for personal project)
- **Approval**: Submit request at developer.garmin.com; 2 business days for approval; 1–4 week integration
- **Key APIs**:
  - **Activity API**: Detailed workout data (pace, cadence, power, HR, GPS track)
  - **Health API**: Sleep stages, HRV, resting HR, stress, SpO2, body battery, steps
  - **Training API**: Push workouts and training plans to Garmin Connect calendar → syncs to device
  - **Courses API**: Push GPS courses to device
- **Prototyping shortcut**: Use `python-garminconnect` (unofficial community library) for local development before Garmin approval

### Weather APIs (Dual-source for Malaysia)

**Open-Meteo** (global model, reliable for temperature/humidity/wind in tropics):
- **Cost**: Free, no API key
- **Endpoint**: `https://api.open-meteo.com/v1/forecast`
- **Best for**: Apparent temperature, humidity, wind speed — the variables used for pace adjustment. ECMWF IFS at 9 km resolution globally.
- **Limitation**: Convective afternoon thunderstorm prediction is unreliable — this is a known limitation of all global models in tropical SEA.

**MET Malaysia API** (local source, accurate for rain warnings):
- **Cost**: Free, no API key
- **Endpoint**: `https://api.data.gov.my/weather/forecast`
- **Best for**: Rain warnings, weather alerts, 7-day general forecast from Malaysian Meteorological Department (official ground-truth data)
- **Docs**: https://developer.data.gov.my/realtime-api/weather

---

## Data Architecture

### PostgreSQL Schema (Neon)

```sql
-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Athletes
CREATE TABLE athletes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  name TEXT,
  strava_athlete_id BIGINT UNIQUE,
  garmin_user_id TEXT UNIQUE,
  timezone TEXT DEFAULT 'Asia/Kuala_Lumpur',
  goal_race_type TEXT,              -- 'half_marathon' | 'marathon'
  goal_race_date DATE,
  goal_finish_time_seconds INT,
  gemini_api_key_encrypted TEXT,    -- AES-256 encrypted; NULL until user provides key
  gemini_model TEXT DEFAULT 'gemini-2.5-flash',  -- user can choose model
  created_at TIMESTAMPTZ DEFAULT now()
);

-- OAuth tokens
CREATE TABLE oauth_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id UUID REFERENCES athletes(id) ON DELETE CASCADE,
  provider TEXT NOT NULL,           -- 'strava' | 'garmin'
  access_token TEXT NOT NULL,
  refresh_token TEXT,
  expires_at TIMESTAMPTZ,
  scope TEXT,
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Normalised activities (from Strava + Garmin, merged)
CREATE TABLE activities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id UUID REFERENCES athletes(id) ON DELETE CASCADE,
  source TEXT NOT NULL,             -- 'strava' | 'garmin'
  external_id TEXT,                 -- original source ID
  activity_type TEXT NOT NULL,      -- 'run' | 'ride' | etc.
  started_at TIMESTAMPTZ NOT NULL,
  duration_seconds INT,
  distance_meters FLOAT,
  elevation_gain_meters FLOAT,
  avg_hr INT,
  max_hr INT,
  avg_pace_seconds_per_km FLOAT,
  avg_cadence INT,
  avg_power INT,
  hr_zone_distribution JSONB,       -- {z1: 0.15, z2: 0.30, ...}
  splits JSONB,                     -- per-km split data
  workout_type TEXT,                -- 'easy' | 'tempo' | 'long_run' | 'interval' | 'race'
  perceived_effort INT,             -- 1–10 RPE
  notes TEXT,
  gear_id TEXT,
  raw_metadata JSONB,               -- store original payload for debugging
  UNIQUE(source, external_id)
);
SELECT create_hypertable('activities', 'started_at');

-- Daily health metrics (from Garmin Health API)
CREATE TABLE health_metrics (
  athlete_id UUID REFERENCES athletes(id) ON DELETE CASCADE,
  recorded_date DATE NOT NULL,
  hrv_rmssd FLOAT,                  -- ms
  hrv_sdrr FLOAT,
  resting_hr INT,
  sleep_score INT,                  -- 0–100 Garmin score
  sleep_duration_minutes INT,
  deep_sleep_minutes INT,
  rem_sleep_minutes INT,
  sleep_start TIMESTAMPTZ,
  sleep_end TIMESTAMPTZ,
  body_battery_max INT,
  body_battery_min INT,
  stress_avg INT,
  steps INT,
  spo2_avg FLOAT,
  respiratory_rate FLOAT,
  training_readiness_score INT,     -- Garmin's own composite
  PRIMARY KEY (athlete_id, recorded_date)
);

-- Computed daily readiness (our own composite)
CREATE TABLE readiness_scores (
  athlete_id UUID REFERENCES athletes(id) ON DELETE CASCADE,
  score_date DATE NOT NULL,
  readiness_score FLOAT,            -- 0–100
  hrv_delta_pct FLOAT,              -- % vs 30-day baseline
  sleep_delta_pct FLOAT,
  load_delta_pct FLOAT,
  ai_summary TEXT,                  -- 3-bullet AI readiness brief
  ai_recommendation TEXT,
  PRIMARY KEY (athlete_id, score_date)
);

-- Training plans
CREATE TABLE training_plans (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id UUID REFERENCES athletes(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT now(),
  valid_from DATE NOT NULL,
  valid_to DATE NOT NULL,
  goal_race_type TEXT,
  goal_race_date DATE,
  goal_time_seconds INT,
  status TEXT DEFAULT 'active',     -- 'active' | 'superseded' | 'completed'
  plan_summary TEXT,                -- AI narrative: how to execute the plan
  revision_reason TEXT,             -- why was this version generated
  weekly_structure JSONB            -- high-level periodisation notes
);

-- Individual planned workouts
CREATE TABLE planned_workouts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  plan_id UUID REFERENCES training_plans(id) ON DELETE CASCADE,
  athlete_id UUID REFERENCES athletes(id) ON DELETE CASCADE,
  scheduled_date DATE NOT NULL,
  workout_type TEXT NOT NULL,       -- 'easy' | 'long_run' | 'tempo' | 'interval' | 'rest' | 'race'
  title TEXT NOT NULL,
  description TEXT,
  target_distance_meters FLOAT,
  target_duration_minutes INT,
  target_pace_min_seconds_per_km FLOAT,
  target_pace_max_seconds_per_km FLOAT,
  target_hr_zone INT,               -- 1–5
  target_rpe INT,                   -- 1–10
  intensity_points FLOAT,           -- TSS equivalent
  completed BOOLEAN DEFAULT false,
  completed_activity_id UUID REFERENCES activities(id),
  calendar_event_id TEXT,           -- Google Calendar event ID
  garmin_workout_id TEXT            -- Garmin Training API workout ID
);

-- Shoe / gear tracker
CREATE TABLE gear (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id UUID REFERENCES athletes(id) ON DELETE CASCADE,
  strava_gear_id TEXT UNIQUE,
  name TEXT NOT NULL,
  brand TEXT,
  model TEXT,
  distance_meters FLOAT DEFAULT 0,
  max_distance_meters FLOAT DEFAULT 800000, -- 800km default retirement
  is_active BOOLEAN DEFAULT true,
  purchased_at DATE,
  retired_at DATE
);

-- RAG vector store: activity summaries
CREATE TABLE activity_embeddings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  activity_id UUID REFERENCES activities(id) ON DELETE CASCADE,
  athlete_id UUID REFERENCES athletes(id) ON DELETE CASCADE,
  content TEXT NOT NULL,            -- human-readable summary used as RAG chunk
  embedding VECTOR(384),             -- all-MiniLM-L6-v2 local model dimensions
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON activity_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- RAG vector store: coaching knowledge base
CREATE TABLE knowledge_embeddings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source TEXT,                      -- 'daniels_running_formula' | 'polarised_training' | etc.
  chunk_index INT,
  content TEXT NOT NULL,
  embedding VECTOR(384),             -- all-MiniLM-L6-v2 local model dimensions
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON knowledge_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);
```

### Key Indexes and Continuous Aggregates

```sql
-- Fast lookups by athlete + date range
CREATE INDEX idx_activities_athlete_date ON activities(athlete_id, started_at DESC);
CREATE INDEX idx_health_athlete_date ON health_metrics(athlete_id, recorded_date DESC);
CREATE INDEX idx_planned_athlete_date ON planned_workouts(athlete_id, scheduled_date);

-- Weekly mileage aggregate (TimescaleDB)
CREATE MATERIALIZED VIEW weekly_mileage
WITH (timescaledb.continuous) AS
SELECT
  athlete_id,
  time_bucket('7 days', started_at) AS week,
  SUM(distance_meters) / 1000 AS km,
  SUM(duration_seconds) / 3600.0 AS hours,
  AVG(avg_hr) AS avg_hr,
  COUNT(*) AS activity_count
FROM activities
WHERE activity_type = 'run'
GROUP BY athlete_id, week;
```

---

## Backend — FastAPI

### Project Structure

```
backend/
├── main.py
├── config.py                 # env vars, settings
├── database.py               # SQLAlchemy async engine, Neon connection string
├── models/
│   ├── athlete.py
│   ├── activity.py
│   ├── health.py
│   ├── plan.py
│   └── gear.py
├── routers/
│   ├── auth.py               # OAuth flows for Strava + Garmin
│   ├── settings.py           # Gemini key management, user preferences
│   ├── activities.py         # CRUD + sync
│   ├── health.py             # health metrics endpoints
│   ├── plans.py              # training plan CRUD + generation
│   ├── dashboard.py          # aggregated stats for frontend
│   ├── analysis.py           # race predictor, segment analysis
│   └── calendar.py           # Google Calendar + Garmin Training API
├── services/
│   ├── strava_client.py      # Strava API wrapper
│   ├── garmin_client.py      # Garmin API wrapper
│   ├── weather_client.py     # Dual-source weather: Open-Meteo (temp/humidity) + MET Malaysia (rain warnings)
│   ├── sync_service.py       # orchestrates data ingestion
│   ├── gemini_client.py      # Gemini API wrapper with rate-limit layer
│   ├── rate_limiter.py       # token bucket + Redis counters for RPM/RPD
│   ├── ai_service.py         # high-level AI calls (uses gemini_client)
│   ├── rag_service.py        # vector similarity search, context retrieval
│   ├── plan_service.py       # training plan generation + adaptive revision
│   ├── readiness_service.py  # daily readiness scoring pipeline
│   ├── race_predictor.py     # Riegel formula + AI analysis
│   └── scheduler.py          # APScheduler jobs
├── prompts/
│   ├── training_plan.py      # plan generation prompt templates
│   ├── daily_brief.py        # health digest prompt templates
│   ├── race_analysis.py      # post-race retrospective templates
│   └── shared.py             # athlete context builder (shared across prompts)
└── utils/
    ├── pace.py               # pace/speed conversion helpers
    ├── hrv.py                # HRV baseline calculation
    ├── load.py               # ATL/CTL/TSB training load calculations
    ├── embeddings.py         # text → embedding helpers
    └── encryption.py         # AES-256 encrypt/decrypt for user API keys
```

### Key Environment Variables

```bash
DATABASE_URL=postgresql+asyncpg://...   # Neon connection string
REDIS_URL=redis://...                   # Upstash Redis URL
GEMINI_ENCRYPTION_KEY=...              # generate: python -c "import secrets; print(secrets.token_hex(32))"
# NOTE: No GEMINI_API_KEY — users provide their own via the Settings page in the app
STRAVA_CLIENT_ID=...
STRAVA_CLIENT_SECRET=...
GARMIN_CLIENT_ID=...
GARMIN_CLIENT_SECRET=...
GOOGLE_CALENDAR_CLIENT_ID=...
GOOGLE_CALENDAR_CLIENT_SECRET=...
JWT_SECRET=...                          # generate: python -c "import secrets; print(secrets.token_hex(32))"
OPEN_METEO_BASE_URL=https://api.open-meteo.com/v1
```

---

## Data Sync Pipeline

### Strava Sync

1. Register a Strava webhook subscription on app startup (`POST /push_subscriptions`)
2. On `activity:create` webhook event → fetch full activity detail → normalise → upsert into `activities`
3. Run backfill on first OAuth connect: fetch last 90 days of activities in paginated batches (respect 200 req/15min limit)
4. After each activity upsert → generate activity embedding → store in `activity_embeddings`

### Garmin Sync

1. On OAuth connect → backfill last 90 days via Activity API and Health API
2. Schedule daily cron at 06:00 local time → fetch yesterday's health metrics → upsert into `health_metrics`
3. After health upsert → trigger readiness score computation for that day

### Data Normalisation Rules

- Always store distances in **metres**, durations in **seconds**, pace in **seconds/km**
- Strava speed (m/s) → pace: `pace_sec_per_km = 1000 / speed_mps`
- Garmin HR zone data → normalise to zones 1–5 regardless of source zone schema
- Never pass raw API response JSON to Gemini — always use the normalised schema fields

---

## Gemini API Integration — User-Provided Key Architecture

### How it works

Each user provides their own Gemini API key obtained free from Google AI Studio. This means:
- The app holds **no master Gemini key** — zero shared quota
- Each user gets the full Gemini free tier (250 RPD Flash, 1,000 RPD Flash-Lite) for themselves
- The key is encrypted at rest using AES-256 and stored in `athletes.gemini_api_key_encrypted`
- It is decrypted in memory only at the moment of an API call, never logged or exposed

### `utils/encryption.py`

```python
from cryptography.fernet import Fernet
import base64
import hashlib
from config import settings

def _get_cipher() -> Fernet:
    # Derive a 32-byte Fernet key from the GEMINI_ENCRYPTION_KEY env var
    key = hashlib.sha256(settings.GEMINI_ENCRYPTION_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))

def encrypt_api_key(plaintext: str) -> str:
    return _get_cipher().encrypt(plaintext.encode()).decode()

def decrypt_api_key(ciphertext: str) -> str:
    return _get_cipher().decrypt(ciphertext.encode()).decode()
```

### Settings page — API key onboarding flow

When a user has not yet provided a Gemini key, the app shows an **onboarding banner** on the Overview page:

```
┌─────────────────────────────────────────────────────┐
│  ⚡ Enable AI features                               │
│  Add your free Gemini API key to unlock training     │
│  coaching, health analysis, and race planning.       │
│  [Get free key →]        [Add key]                   │
└─────────────────────────────────────────────────────┘
```

The Settings page has an **AI Configuration** section:
- Input field: "Gemini API key" (type=password, masked)
- Helper text: "Get your free key at aistudio.google.com — no credit card needed"
- [Test connection] button — calls `/settings/gemini/test` before saving
- Model selector: Flash (recommended) or Flash-Lite (faster, more quota)
- Once saved: shows "✓ Connected · Gemini 2.5 Flash" with a [Remove] option

### `routers/settings.py`

```python
@router.post("/settings/gemini/key")
async def save_gemini_key(
    body: GeminiKeyInput,
    athlete: Athlete = Depends(get_current_athlete),
    db: AsyncSession = Depends(get_db),
):
    # 1. Validate the key works before saving
    valid = await test_gemini_key(body.api_key)
    if not valid:
        raise HTTPException(400, "Invalid Gemini API key — please check and try again")

    # 2. Encrypt and store
    encrypted = encrypt_api_key(body.api_key)
    athlete.gemini_api_key_encrypted = encrypted
    athlete.gemini_model = body.model or "gemini-2.5-flash"
    await db.commit()
    return {"status": "connected", "model": athlete.gemini_model}


@router.post("/settings/gemini/test")
async def test_gemini_key_endpoint(
    body: GeminiKeyInput,
    athlete: Athlete = Depends(get_current_athlete),
):
    valid = await test_gemini_key(body.api_key)
    return {"valid": valid}


@router.delete("/settings/gemini/key")
async def remove_gemini_key(
    athlete: Athlete = Depends(get_current_athlete),
    db: AsyncSession = Depends(get_db),
):
    athlete.gemini_api_key_encrypted = None
    await db.commit()
    return {"status": "removed"}


async def test_gemini_key(api_key: str) -> bool:
    """Send a minimal test prompt to verify the key is valid."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent",
                params={"key": api_key},
                json={"contents": [{"role": "user", "parts": [{"text": "Reply with OK"}]}],
                      "generationConfig": {"maxOutputTokens": 5}},
            )
            return r.status_code == 200
    except Exception:
        return False
```

### Updated `dependencies.py` — key fetched per request from DB

```python
async def get_gemini_client(
    athlete: Athlete = Depends(get_current_athlete),
) -> GeminiClient:
    if not athlete.gemini_api_key_encrypted:
        raise HTTPException(
            status_code=403,
            detail="Gemini API key not configured. Add your key in Settings.",
            headers={"X-Error-Code": "GEMINI_KEY_MISSING"}
        )
    api_key = decrypt_api_key(athlete.gemini_api_key_encrypted)
    rate_limiter = GeminiRateLimiter(athlete_id=str(athlete.id))  # per-user bucket
    return GeminiClient(api_key=api_key, rate_limiter=rate_limiter)

async def get_ai_service(gemini: GeminiClient = Depends(get_gemini_client)) -> AIService:
    return AIService(gemini)
```

### Updated `services/gemini_client.py` — accepts key per instance

```python
class GeminiClient:
    def __init__(self, api_key: str, rate_limiter: GeminiRateLimiter):
        self.api_key = api_key   # decrypted at call time, not stored globally
        self.rl = rate_limiter
        self.http = httpx.AsyncClient(timeout=60.0)
    # ... rest unchanged
```

### Updated `services/rate_limiter.py` — per-user buckets

```python
class GeminiRateLimiter:
    # Key buckets by athlete_id, not globally
    _buckets: dict[str, dict] = {}   # athlete_id → model → bucket

    def __init__(self, athlete_id: str):
        self.athlete_id = athlete_id
        key = athlete_id
        if key not in self._buckets:
            self._buckets[key] = {}
            for model, limits in MODEL_LIMITS.items():
                safe_rpm = int(limits.rpm * SAFETY_FACTOR)
                self._buckets[key][model] = {
                    "tokens": safe_rpm,
                    "max_tokens": safe_rpm,
                    "refill_rate": safe_rpm / 60.0,
                    "last_refill": time.monotonic(),
                    "lock": asyncio.Lock(),
                }
    # acquire() logic unchanged — uses self._buckets[self.athlete_id]
```

### Frontend — AI key missing state

All AI-powered components check for the `GEMINI_KEY_MISSING` error code and render a consistent prompt instead of an error:

```typescript
// frontend/src/components/AIFeatureGate.tsx
export function AIFeatureGate({ children }: { children: React.ReactNode }) {
  const { data: settings } = useQuery({ queryKey: ["settings"], queryFn: api.settings.get })

  if (!settings?.gemini_connected) {
    return (
      <div className="rounded-2xl bg-gray-50 p-4 text-center">
        <p className="text-sm text-gray-500 mb-3">
          Add your Gemini API key to enable AI features
        </p>
        <Link href="/settings#ai" className="text-sm font-semibold" style={{ color: "var(--accent)" }}>
          Set up in Settings →
        </Link>
      </div>
    )
  }

  return <>{children}</>
}

// Usage: wrap any AI-powered card
<AIFeatureGate>
  <DailyBriefCard />
</AIFeatureGate>
```

### Free tier limits (per user, with their own key)

| Model | RPM | RPD | TPM |
|---|---|---|---|
| `gemini-2.5-flash` | 10 | 250 | 250,000 |
| `gemini-2.5-flash-lite` | 15 | 1,000 | 250,000 |

For a solo athlete using the app personally, 250 RPD Flash is far more than needed (~10–15 AI calls/day). The rate limiter now exists purely to absorb RPM bursts, not to ration a shared pool.

### `services/rate_limiter.py`

```python
import asyncio
import time
import redis.asyncio as aioredis
from dataclasses import dataclass
from enum import Enum

class GeminiModel(str, Enum):
    FLASH = "gemini-2.5-flash"
    FLASH_LITE = "gemini-2.5-flash-lite"

@dataclass
class ModelLimits:
    rpm: int        # requests per minute
    rpd: int        # requests per day
    tpm: int        # tokens per minute

MODEL_LIMITS = {
    GeminiModel.FLASH:      ModelLimits(rpm=10,  rpd=250,   tpm=250_000),
    GeminiModel.FLASH_LITE: ModelLimits(rpm=15,  rpd=1_000, tpm=250_000),
}

# Safety margins — stay at 80% of limit to absorb timing jitter
SAFETY_FACTOR = 0.80

class GeminiRateLimiter:
    """
    Two-layer rate limiter:
    Layer 1 — In-process token bucket per model (RPM control, sub-second precision)
    Layer 2 — Redis atomic counters per model per day (RPD control, survives restarts)
    """

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self._buckets: dict[GeminiModel, dict] = {}
        for model, limits in MODEL_LIMITS.items():
            safe_rpm = int(limits.rpm * SAFETY_FACTOR)
            self._buckets[model] = {
                "tokens": safe_rpm,
                "max_tokens": safe_rpm,
                "refill_rate": safe_rpm / 60.0,  # tokens per second
                "last_refill": time.monotonic(),
                "lock": asyncio.Lock(),
            }

    # ── RPM: token bucket ──────────────────────────────────────────────

    async def _acquire_rpm_token(self, model: GeminiModel) -> None:
        bucket = self._buckets[model]
        async with bucket["lock"]:
            while True:
                now = time.monotonic()
                elapsed = now - bucket["last_refill"]
                bucket["tokens"] = min(
                    bucket["max_tokens"],
                    bucket["tokens"] + elapsed * bucket["refill_rate"]
                )
                bucket["last_refill"] = now

                if bucket["tokens"] >= 1:
                    bucket["tokens"] -= 1
                    return

                # Calculate sleep until next token available
                deficit = 1 - bucket["tokens"]
                sleep_s = deficit / bucket["refill_rate"]
                await asyncio.sleep(sleep_s + 0.05)  # +50ms buffer

    # ── RPD: Redis counter ─────────────────────────────────────────────

    async def _acquire_rpd_slot(self, model: GeminiModel) -> bool:
        """Atomically increment daily counter. Returns False if daily limit reached."""
        safe_rpd = int(MODEL_LIMITS[model].rpd * SAFETY_FACTOR)
        key = f"gemini:rpd:{model.value}:{_today_utc()}"

        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, 86_400 + 3_600)  # TTL: 25h (covers midnight boundary)
            count, _ = await pipe.execute()

        return count <= safe_rpd

    # ── Public acquire ─────────────────────────────────────────────────

    async def acquire(self, model: GeminiModel) -> None:
        """
        Block until a request slot is available on both RPM and RPD dimensions.
        Raises GeminiDailyLimitReached if the day's quota is exhausted.
        """
        if not await self._acquire_rpd_slot(model):
            raise GeminiDailyLimitReached(
                f"Daily limit reached for {model.value}. Resets at midnight Pacific."
            )
        await self._acquire_rpm_token(model)

    async def get_daily_usage(self, model: GeminiModel) -> dict:
        key = f"gemini:rpd:{model.value}:{_today_utc()}"
        count = await self.redis.get(key)
        limit = MODEL_LIMITS[model].rpd
        used = int(count) if count else 0
        return {"model": model.value, "used": used, "limit": limit, "remaining": limit - used}


def _today_utc() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class GeminiDailyLimitReached(Exception):
    pass
```

### `services/gemini_client.py`

```python
import asyncio
import httpx
import json
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .rate_limiter import GeminiRateLimiter, GeminiModel, GeminiDailyLimitReached
from config import settings

logger = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiClient:
    def __init__(self, rate_limiter: GeminiRateLimiter):
        self.rl = rate_limiter
        self.http = httpx.AsyncClient(timeout=60.0)

    async def generate(
        self,
        prompt: str,
        model: GeminiModel = GeminiModel.FLASH,
        system_instruction: str | None = None,
        max_output_tokens: int = 1024,
        response_json: bool = False,
    ) -> str:
        """
        Core generate method.
        - Acquires rate-limit slot before calling API.
        - Retries on transient 429/5xx with exponential backoff.
        - Falls back to Flash-Lite if Flash daily limit is exhausted.
        """
        try:
            await self.rl.acquire(model)
        except GeminiDailyLimitReached:
            if model == GeminiModel.FLASH:
                logger.warning("Flash daily limit reached — falling back to Flash-Lite")
                await self.rl.acquire(GeminiModel.FLASH_LITE)
                model = GeminiModel.FLASH_LITE
            else:
                raise

        return await self._call_api(prompt, model, system_instruction, max_output_tokens, response_json)

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    async def _call_api(self, prompt, model, system_instruction, max_output_tokens, response_json):
        url = f"{GEMINI_API_BASE}/{model.value}:generateContent"
        
        contents = [{"role": "user", "parts": [{"text": prompt}]}]
        body = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_output_tokens,
                "temperature": 0.3,
            }
        }
        
        if system_instruction:
            body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        
        if response_json:
            body["generationConfig"]["responseMimeType"] = "application/json"

        response = await self.http.post(
            url,
            params={"key": self.api_key},   # per-user key, not a global setting
            json=body,
        )

        if response.status_code == 429:
            # Surface retry-after header if present
            retry_after = int(response.headers.get("Retry-After", 15))
            logger.warning(f"Gemini 429 received — backing off {retry_after}s")
            await asyncio.sleep(retry_after)
            response.raise_for_status()  # re-raise to trigger tenacity retry

        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    async def generate_structured(self, prompt: str, model: GeminiModel = GeminiModel.FLASH) -> dict:
        """Generate JSON-mode response and parse it."""
        raw = await self.generate(prompt, model=model, response_json=True, max_output_tokens=2048)
        # Strip markdown fences if present
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(clean)

    async def close(self):
        await self.http.aclose()
```

### `services/ai_service.py`

```python
"""
High-level AI service — all features call this, never gemini_client directly.
Chooses the right model per task based on complexity and daily budget.
"""

from .gemini_client import GeminiClient, GeminiModel
from prompts import training_plan, daily_brief, race_analysis, shared


class AIService:
    def __init__(self, gemini: GeminiClient):
        self.gemini = gemini

    # Uses Flash (higher quality) — called once per plan generation
    async def generate_training_plan(self, athlete, recent_activities, health_baseline, rag_context) -> dict:
        prompt = training_plan.build_prompt(athlete, recent_activities, health_baseline, rag_context)
        return await self.gemini.generate_structured(prompt, model=GeminiModel.FLASH)

    # Uses Flash-Lite (faster, more quota) — called daily per athlete
    async def generate_daily_brief(self, metrics, baselines, readiness_score, upcoming_workout) -> str:
        prompt = daily_brief.build_prompt(metrics, baselines, readiness_score, upcoming_workout)
        return await self.gemini.generate(prompt, model=GeminiModel.FLASH_LITE, max_output_tokens=300)

    # Uses Flash — called after each race
    async def generate_race_retrospective(self, race_activity, training_plan, recent_health) -> str:
        prompt = race_analysis.build_retrospective_prompt(race_activity, training_plan, recent_health)
        return await self.gemini.generate(prompt, model=GeminiModel.FLASH, max_output_tokens=800)

    # Uses Flash-Lite — called on plan revision trigger
    async def generate_revision_summary(self, delta_context, new_plan) -> str:
        prompt = f"""
In 2 concise sentences, explain these training plan changes to the athlete:
{delta_context}
Changes made: {new_plan.get('plan_summary', '')}
Be direct and encouraging.
"""
        return await self.gemini.generate(prompt, model=GeminiModel.FLASH_LITE, max_output_tokens=150)

    # Uses Flash — called for race time prediction augmentation
    async def analyse_race_prediction(self, predictions, athlete_context) -> str:
        prompt = race_analysis.build_predictor_prompt(predictions, athlete_context)
        return await self.gemini.generate(prompt, model=GeminiModel.FLASH, max_output_tokens=400)

    async def get_quota_status(self) -> dict:
        """Returns current daily usage for both models — useful for admin dashboard."""
        flash = await self.gemini.rl.get_daily_usage(GeminiModel.FLASH)
        lite = await self.gemini.rl.get_daily_usage(GeminiModel.FLASH_LITE)
        return {"flash": flash, "flash_lite": lite}
```

### Request Queue for Non-Urgent AI Tasks

Background jobs (plan revision, embedding generation, post-race retrospective) should run through a lightweight async queue so they don't compete with interactive requests:

```python
# services/ai_queue.py
import asyncio
from enum import IntEnum

class Priority(IntEnum):
    HIGH = 0    # interactive: user clicked "generate plan"
    NORMAL = 1  # scheduled: daily brief, revision check
    LOW = 2     # background: re-embedding, retrospective after sync

class AIQueue:
    def __init__(self):
        self._queues = {p: asyncio.Queue() for p in Priority}

    async def enqueue(self, coro, priority: Priority = Priority.NORMAL):
        await self._queues[priority].put(coro)

    async def worker(self, ai_service: AIService):
        """Single worker — serialises all AI calls to respect RPM naturally."""
        while True:
            for priority in Priority:  # drain HIGH before NORMAL before LOW
                try:
                    coro = self._queues[priority].get_nowait()
                    await coro
                    break
                except asyncio.QueueEmpty:
                    continue
            else:
                await asyncio.sleep(0.5)
```

### Daily Budget Allocation (Personal Athlete)

| Task | Model | Calls/day | Notes |
|---|---|---|---|
| Morning health brief | Flash-Lite | 1 | Cron at 06:00 |
| Plan revision check | Flash-Lite | 1 | Cron at 07:00 — only calls AI if revision triggered |
| Plan revision (if triggered) | Flash | 0–1 | Triggered ~2–3×/week at most |
| Race predictor (on-demand) | Flash | 0–2 | User-initiated |
| Post-race retrospective | Flash | 0–1 | Auto-triggered on race activity sync |
| Segment trend insight | Flash-Lite | 0–3 | On-demand from dashboard |
| **Daily total** | | **~4–9** | Well within 250 Flash RPD + 1,000 Flash-Lite RPD |

### Graceful Degradation Strategy

When daily quota is exhausted (rare for personal use, but possible):

1. Daily health brief → serve last cached brief with a "quota refreshes at midnight" banner
2. Training plan generation → queue the request for first available slot next day; notify user
3. Dashboard metrics → all charts and stats remain fully functional (no AI dependency)
4. Segment and load charts → fully functional (no AI dependency)

```python
# In routers/plans.py — example graceful degradation
async def generate_plan(athlete_id: str, ai_service: AIService):
    try:
        plan = await ai_service.generate_training_plan(...)
        return {"status": "generated", "plan": plan}
    except GeminiDailyLimitReached:
        # Queue for midnight reset
        await ai_queue.enqueue(
            ai_service.generate_training_plan(...),
            priority=Priority.HIGH
        )
        return {
            "status": "queued",
            "message": "AI quota reached for today. Your plan will be generated automatically after midnight Pacific and you'll be notified."
        }
```

---

## Feature 1 — Training Coach and Planner

### Plan Generation Prompt Architecture

```python
def build_plan_prompt(athlete, recent_activities, health_baseline, rag_context):
    return f"""
You are an expert endurance running coach. Generate a structured training plan in JSON.

ATHLETE PROFILE:
- Goal race: {athlete.goal_race_type} on {athlete.goal_race_date}
- Goal finish time: {format_time(athlete.goal_finish_time_seconds)}
- Weeks to race: {weeks_to_race}
- Current estimated VO2max: {estimated_vo2max}
- Lactate threshold pace: {lthr_pace} min/km

RECENT TRAINING (last 6 weeks):
{format_recent_activities(recent_activities)}  # compressed: date, type, distance, avg HR, pace

HEALTH BASELINES:
- 30-day avg HRV: {health_baseline.hrv_rmssd_avg} ms
- 30-day avg resting HR: {health_baseline.resting_hr_avg} bpm
- Avg sleep score: {health_baseline.sleep_score_avg}
- Current weekly mileage: {current_weekly_km} km

COACHING CONTEXT (from knowledge base):
{rag_context}  # 3–5 retrieved chunks from coaching literature

Generate a {plan_weeks}-week training plan. Return ONLY valid JSON matching this schema:
{{
  "plan_summary": "string — plain English explanation of the periodisation approach",
  "weekly_structure": "string — base/build/peak/taper breakdown",
  "workouts": [
    {{
      "date": "YYYY-MM-DD",
      "type": "easy|long_run|tempo|interval|rest|race",
      "title": "string",
      "description": "string",
      "distance_meters": number | null,
      "duration_minutes": number | null,
      "pace_min_sec_per_km": number | null,
      "pace_max_sec_per_km": number | null,
      "hr_zone": 1-5 | null,
      "rpe": 1-10,
      "intensity_points": number
    }}
  ]
}}
"""
```

### Adaptive Revision Trigger Conditions

The revision engine runs as a daily background job and re-generates the plan if **any** of:

- A scheduled workout was missed (no matching activity within 6 hours of scheduled time)
- Last night's sleep score < athlete's 30-day baseline × 0.80
- Today's HRV < athlete's 30-day baseline × 0.88 (more than 12% suppressed)
- Training load (ATL) spiked >30% above target for the week
- A completed workout's HR was consistently >10 bpm above zone target (possible illness/overtraining signal)

When revision triggers, the prompt includes the delta:
```
REVISION CONTEXT:
- Missed workout: Tuesday tempo (8km @ threshold pace) — not completed
- HRV suppressed: 42ms today vs 55ms baseline (-24%)
The plan below supersedes the previous version. Explain adjustments in plan_summary.
```

### Calendar Export

```python
# Google Calendar API
def push_to_google_calendar(workout, athlete_token):
    event = {
        "summary": workout.title,
        "description": workout.description,
        "start": {"date": str(workout.scheduled_date)},
        "end": {"date": str(workout.scheduled_date)},
        "colorId": COLOR_MAP[workout.workout_type]  # easy=green, tempo=yellow, intervals=red
    }

# Garmin Training API
def push_to_garmin(workout, garmin_token):
    # Builds a structured workout with step-by-step instructions
    # syncs to Garmin device via Garmin Connect
    pass

# ICS export (always available, no auth)
def export_ics(plan_workouts):
    # Returns .ics file download
    pass
```

---

## Feature 2 — Health and Training Analyst

### Daily Readiness Pipeline (runs at 06:00 local time)

```python
async def compute_daily_readiness(athlete_id, score_date):
    # 1. Fetch today's health metrics
    metrics = await get_health_metrics(athlete_id, score_date)
    
    # 2. Compute baselines (rolling 30-day avg)
    baselines = await compute_baselines(athlete_id, days=30)
    
    # 3. Compute composite readiness score (0–100)
    hrv_delta = (metrics.hrv_rmssd - baselines.hrv_avg) / baselines.hrv_avg
    sleep_delta = (metrics.sleep_score - baselines.sleep_avg) / baselines.sleep_avg
    load_delta = (current_atl - target_atl) / target_atl
    
    readiness = 50 + (hrv_delta * 25) + (sleep_delta * 15) - (max(0, load_delta) * 10)
    readiness = max(0, min(100, readiness))
    
    # 4. Build AI brief
    prompt = build_daily_brief_prompt(metrics, baselines, readiness, upcoming_workout)
    ai_brief = await ai_service.generate_daily_brief(metrics, baselines, readiness, upcoming_workout)
    
    # 5. Persist
    await upsert_readiness_score(athlete_id, score_date, readiness, ai_brief)
    
    # 6. Push notification / email
    await send_morning_digest(athlete_id, readiness, ai_brief)
```

### Daily Brief Prompt

```python
def build_daily_brief_prompt(metrics, baselines, readiness_score, upcoming_workout):
    return f"""
You are an endurance sports physiologist reviewing an athlete's morning data.

TODAY'S BIOMETRICS:
- HRV: {metrics.hrv_rmssd}ms ({delta_pct(metrics.hrv_rmssd, baselines.hrv_avg):+.0f}% vs 30-day avg of {baselines.hrv_avg:.0f}ms)
- Resting HR: {metrics.resting_hr} bpm ({delta_pct(metrics.resting_hr, baselines.rhr_avg):+.0f}% vs avg)
- Sleep: {metrics.sleep_duration_minutes//60}h {metrics.sleep_duration_minutes%60}m — Score: {metrics.sleep_score}/100
- Deep sleep: {metrics.deep_sleep_minutes}min | REM: {metrics.rem_sleep_minutes}min
- Body battery: {metrics.body_battery_max}/100 (peak)
- Overall readiness score: {readiness_score:.0f}/100

TODAY'S PLANNED WORKOUT:
{upcoming_workout.title} — {upcoming_workout.description}

Write exactly 3 bullet points:
1. Recovery status (what the numbers mean in plain language)
2. Today's training recommendation (proceed as planned / modify / rest — with specific pace/HR guidance if modifying)
3. One actionable tip for today (sleep, nutrition, warm-up, or mental)

Keep each bullet under 30 words. Be direct, data-specific, and coach-like.
"""
```

---

## Feature 3 — Race Predictor

### Implementation

```python
def riegel_predict(known_distance_m, known_time_s, target_distance_m, fatigue_factor=1.06):
    """Riegel formula: T2 = T1 × (D2/D1)^fatigue_factor"""
    return known_time_s * (target_distance_m / known_distance_m) ** fatigue_factor

async def predict_race_time(athlete_id, target_race_type):
    # 1. Find best recent performances (last 90 days)
    recent_races = await get_recent_race_efforts(athlete_id, days=90)
    
    # 2. Riegel predictions from each reference distance
    predictions = []
    for effort in recent_races:
        pred = riegel_predict(effort.distance_m, effort.time_s, TARGET_DISTANCES[target_race_type])
        predictions.append({
            "reference": effort,
            "predicted_seconds": pred,
            "confidence": compute_confidence(effort)  # penalise old/short efforts
        })
    
    # 3. Weighted average prediction
    weighted_pred = weighted_average([p["predicted_seconds"] for p in predictions],
                                      [p["confidence"] for p in predictions])
    
    # 4. AI-augmented prediction: pass training context for qualitative adjustment
    ai_analysis = await ai_service.analyse_race_prediction(predictions, athlete_context)
    
    return {"predicted_time": weighted_pred, "ai_analysis": ai_analysis, "breakdown": predictions}
```

---

## Feature 4 — Segment Performance Tracking

### Implementation

```python
# On each Strava activity sync, extract segment efforts
async def sync_segment_efforts(activity_strava_id, athlete_id):
    detailed = await strava_client.get_activity(activity_strava_id)
    for effort in detailed.segment_efforts:
        await upsert_segment_effort(
            athlete_id=athlete_id,
            segment_id=effort.segment.id,
            segment_name=effort.segment.name,
            elapsed_seconds=effort.elapsed_time,
            avg_hr=effort.average_heartrate,
            activity_date=effort.start_date
        )

# Dashboard query: trend of a segment over time
async def get_segment_trend(athlete_id, segment_id, days=180):
    return await db.fetch_all("""
        SELECT activity_date, elapsed_seconds, avg_hr,
               AVG(elapsed_seconds) OVER (ORDER BY activity_date ROWS 4 PRECEDING) AS moving_avg
        FROM segment_efforts
        WHERE athlete_id = :athlete_id AND segment_id = :segment_id
          AND activity_date >= NOW() - INTERVAL ':days days'
        ORDER BY activity_date
    """, {"athlete_id": athlete_id, "segment_id": segment_id, "days": days})
```

---

## Feature 5 — Training Load Visualisation (PMC Chart)

### ATL / CTL / TSB Calculation

```python
def compute_training_load(activities_df):
    """
    ATL (Acute Training Load) = 7-day exponential weighted avg of daily TSS — fatigue
    CTL (Chronic Training Load) = 42-day exponential weighted avg — fitness
    TSB (Training Stress Balance) = CTL - ATL — form/freshness
    """
    # Compute daily TSS from intensity_points (already stored per workout)
    daily_tss = activities_df.groupby('date')['intensity_points'].sum().reindex(date_range, fill_value=0)
    
    atl = daily_tss.ewm(span=7, adjust=False).mean()
    ctl = daily_tss.ewm(span=42, adjust=False).mean()
    tsb = ctl - atl
    
    return pd.DataFrame({'atl': atl, 'ctl': ctl, 'tsb': tsb, 'tss': daily_tss})
```

### TSS Calculation per Workout Type

```python
def estimate_tss(activity):
    if activity.avg_power:
        # Cycling: TSS = (duration_s × NP × IF) / (FTP × 3600) × 100
        pass
    else:
        # Running: hrTSS using Daniels' TRIMPS formula
        # hrTSS = duration_hours × avg_hr_ratio × e^(1.92 × avg_hr_ratio) × 64.84
        hr_ratio = activity.avg_hr / athlete.lthr
        return (activity.duration_seconds / 3600) * hr_ratio * math.exp(1.92 * hr_ratio) * 64.84
```

---

## Feature 6 — Weather-Adjusted Planning

### Integration (Dual-source: Open-Meteo + MET Malaysia)

```python
# services/weather_client.py

import httpx
from dataclasses import dataclass

@dataclass
class WorkoutWeather:
    apparent_temp_c: float       # from Open-Meteo (reliable)
    humidity_pct: float          # from Open-Meteo (reliable)
    windspeed_kmh: float         # from Open-Meteo (reliable)
    rain_warning: bool           # from MET Malaysia (more accurate locally)
    rain_warning_text: str | None
    rain_probability_pct: float  # from Open-Meteo (fallback indicator)
    source_note: str             # shown in UI: "Temp/humidity: Open-Meteo · Rain: MET Malaysia"


async def get_workout_weather(scheduled_date, athlete_location) -> WorkoutWeather:
    """
    Dual-source weather fetch optimised for Malaysia:
    - Open-Meteo: temperature, apparent temp, humidity, wind (ECMWF IFS 9km — globally reliable)
    - MET Malaysia: rain warnings from local meteorological stations (more accurate for SEA convective rain)
    Both are free with no API key.
    """
    open_meteo, met_malaysia = await asyncio.gather(
        _fetch_open_meteo(scheduled_date, athlete_location),
        _fetch_met_malaysia(athlete_location.state),
        return_exceptions=True  # don't fail if one source is down
    )

    # Open-Meteo: temperature, humidity, wind for the workout time window (06:00–10:00 local)
    om = open_meteo if not isinstance(open_meteo, Exception) else None
    mm = met_malaysia if not isinstance(met_malaysia, Exception) else None

    return WorkoutWeather(
        apparent_temp_c=_morning_avg(om, "apparent_temperature") if om else 30.0,
        humidity_pct=_morning_avg(om, "relative_humidity_2m") if om else 85.0,
        windspeed_kmh=_morning_avg(om, "windspeed_10m") if om else 10.0,
        rain_warning=mm.has_warning if mm else False,
        rain_warning_text=mm.warning_text if mm else None,
        rain_probability_pct=_morning_avg(om, "precipitation_probability") if om else 0.0,
        source_note="Temp/humidity: Open-Meteo (ECMWF) · Rain alerts: MET Malaysia"
    )


async def _fetch_open_meteo(scheduled_date, location) -> dict:
    params = {
        "latitude": location.lat,
        "longitude": location.lng,
        "hourly": [
            "apparent_temperature",
            "relative_humidity_2m",
            "windspeed_10m",
            "precipitation_probability",
        ],
        "timezone": "Asia/Kuala_Lumpur",
        "start_date": str(scheduled_date),
        "end_date": str(scheduled_date),
        "models": "best_match",   # Open-Meteo picks best available model for the region
    }
    async with httpx.AsyncClient() as client:
        r = await client.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=10)
        r.raise_for_status()
        return r.json()


async def _fetch_met_malaysia(state: str) -> "MetMalaysiaForecast":
    """
    MET Malaysia open API — data.gov.my
    Returns 7-day general forecast and active weather warnings per state.
    No API key required.
    """
    async with httpx.AsyncClient() as client:
        # Fetch warnings
        warn_r = await client.get(
            "https://api.data.gov.my/weather/warning",
            params={"contains": state},
            timeout=10
        )
        warn_r.raise_for_status()
        warnings = warn_r.json().get("data", [])

        # Fetch general forecast for the state
        fc_r = await client.get(
            "https://api.data.gov.my/weather/forecast",
            params={"contains": state, "limit": 7},
            timeout=10
        )
        fc_r.raise_for_status()
        forecast = fc_r.json().get("data", [])

    active_warnings = [w for w in warnings if w.get("valid_to") >= _today_str()]
    return MetMalaysiaForecast(
        has_warning=len(active_warnings) > 0,
        warning_text=active_warnings[0].get("warning_title") if active_warnings else None,
        forecast_summary=forecast[0].get("summary_forecast", "") if forecast else "",
    )


def _morning_avg(om_data: dict, variable: str) -> float:
    """Average the variable over 06:00–10:00 local time (typical morning run window in Malaysia)."""
    hourly = om_data.get("hourly", {})
    times = hourly.get("time", [])
    values = hourly.get(variable, [])
    morning = [v for t, v in zip(times, values) if "T06" <= t[-5:] <= "T10" and v is not None]
    return sum(morning) / len(morning) if morning else values[6] if values else 30.0


def apply_weather_adjustment(workout, weather: WorkoutWeather):
    """
    Pace and effort adjustments for Malaysia's tropical conditions.
    Malaysia baseline: always hot and humid, so thresholds are set for tropical reality.

    Rules (based on exercise physiology for tropical running):
    - Apparent temp > 28°C: start adjusting (tropical baseline is 28–32°C)
    - Apparent temp 28–32°C + humidity > 75%: +8–15 sec/km
    - Apparent temp 32–36°C: +15–25 sec/km, reduce intensity target
    - Apparent temp > 36°C: recommend treadmill or rest day
    - Humidity > 85%: add extra +5 sec/km regardless of temp (Malaysia is regularly 80–90%)
    - Active MET Malaysia rain warning: flag workout, suggest indoor alternative
    """
    adjusted_pace = workout.target_pace_min_sec_per_km
    notes = []
    recommendations = []

    # Temperature adjustment
    if weather.apparent_temp_c > 36:
        recommendations.append("Treadmill or rest recommended — dangerous heat index")
        adjusted_pace += 30
    elif weather.apparent_temp_c > 32:
        heat_penalty = ((weather.apparent_temp_c - 28) / 4) * 10
        adjusted_pace += heat_penalty
        notes.append(f"Heat: +{heat_penalty:.0f}s/km (feels like {weather.apparent_temp_c:.0f}°C)")
    elif weather.apparent_temp_c > 28:
        heat_penalty = ((weather.apparent_temp_c - 28) / 4) * 8
        adjusted_pace += heat_penalty
        notes.append(f"Warm: +{heat_penalty:.0f}s/km")

    # Humidity surcharge (Malaysia often 80–90% even at 6am)
    if weather.humidity_pct > 85:
        adjusted_pace += 5
        notes.append(f"High humidity ({weather.humidity_pct:.0f}%): +5s/km")

    # MET Malaysia rain warning
    if weather.rain_warning:
        recommendations.append(f"MET Malaysia alert: {weather.rain_warning_text} — consider treadmill")

    return adjusted_pace, notes, recommendations
```

---

## Feature 7 — Post-Race Retrospective

### Trigger
Automatically triggered when an activity is synced that matches a planned race workout (within 3 days of scheduled date, distance within 10% of target).

### Retrospective Prompt

```python
def build_retrospective_prompt(race_activity, training_plan, recent_health):
    return f"""
You are an elite endurance running coach conducting a post-race debrief.

RACE RESULT:
- Race: {race_activity.workout_type} — {format_distance(race_activity.distance_meters)}
- Finish time: {format_time(race_activity.duration_seconds)} (goal: {format_time(target_time)})
- Avg pace: {format_pace(race_activity.avg_pace_seconds_per_km)}/km
- Avg HR: {race_activity.avg_hr} bpm | Max HR: {race_activity.max_hr} bpm
- Pacing splits: {format_splits(race_activity.splits)}  # km-by-km breakdown

PRE-RACE READINESS (3 days before):
- Avg HRV: {pre_race_hrv}ms vs baseline {baseline_hrv}ms
- Sleep scores: {pre_race_sleep_scores}
- Body battery peak: {pre_race_body_battery}

TRAINING BUILD (last 12 weeks):
- Peak weekly mileage: {peak_weekly_km} km
- Longest run: {longest_run_km} km
- Tempo sessions completed: {tempo_count} / {tempo_planned}

Generate a structured race retrospective with:
1. Performance summary (2 sentences)
2. Pacing analysis: was it positive split, negative split, or even? What does the HR drift tell us?
3. What worked well (2–3 points)
4. What to improve (2–3 points)  
5. Next training block priorities (3 concrete recommendations)

Be specific, cite the data, be direct.
"""
```

---

## RAG Implementation

### When RAG is Used

| Use case | What's retrieved |
|---|---|
| Training plan generation | Coaching framework chunks (Daniels, polarised training, periodisation) |
| Training plan generation | Athlete's own 12-week activity history as semantic summaries |
| Race predictor | Athlete's past race efforts and best segment performances |
| Daily brief | Athlete's recent 14-day health + activity patterns |

### Activity Summary Generation (for embedding)

```python
def generate_activity_summary(activity, health_on_day):
    """Produces a text chunk that encodes training context for embedding"""
    return f"""
{activity.started_at.strftime('%Y-%m-%d')} {activity.workout_type} run:
{activity.distance_meters/1000:.1f} km in {format_time(activity.duration_seconds)} at {format_pace(activity.avg_pace_seconds_per_km)}/km avg pace.
HR avg {activity.avg_hr}, max {activity.max_hr}. Zone distribution: {activity.hr_zone_distribution}.
RPE: {activity.perceived_effort}/10. Notes: {activity.notes or 'none'}.
Recovery context: HRV {health_on_day.hrv_rmssd:.0f}ms, sleep score {health_on_day.sleep_score}, body battery {health_on_day.body_battery_max}.
""".strip()
```

### Embedding Generation (Local, Free)

Embeddings are generated locally using `sentence-transformers` — no API calls, no cost.

```python
# utils/embeddings.py
from sentence_transformers import SentenceTransformer
import numpy as np

_model = None

def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        # Downloads ~90MB on first run, then cached locally
        _model = SentenceTransformer("all-MiniLM-L6-v2")  # 384-dim output
    return _model

def embed(text: str) -> list[float]:
    model = get_embedding_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()

def embed_batch(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    embeddings = model.encode(texts, normalize_embeddings=True, batch_size=32)
    return embeddings.tolist()
```
### Retrieval

```python
async def retrieve_relevant_context(query_text, athlete_id, top_k=5):
    query_embedding = embed(query_text)  # local, synchronous, free

    results = await db.fetch_all("""
        SELECT content, 1 - (embedding <=> :query_embedding) AS similarity
        FROM activity_embeddings
        WHERE athlete_id = :athlete_id
        ORDER BY embedding <=> :query_embedding
        LIMIT :top_k
    """, {"query_embedding": query_embedding, "athlete_id": athlete_id, "top_k": top_k})
    
    return [r["content"] for r in results if r["similarity"] > 0.75]
```

---

## Frontend — Next.js

### Route Structure

```
app/
├── (auth)/
│   ├── login/page.tsx
│   └── connect/page.tsx          # Strava + Garmin OAuth connect
├── dashboard/
│   ├── page.tsx                  # Today's overview: readiness, next workout, recent activity
│   ├── training/
│   │   ├── page.tsx              # Calendar view of training plan
│   │   ├── plan/page.tsx         # Plan summary + narrative
│   │   └── load/page.tsx         # PMC chart (ATL/CTL/TSB)
│   ├── health/
│   │   ├── page.tsx              # HRV trend, sleep trend, readiness history
│   │   └── [date]/page.tsx       # Daily health detail
│   ├── activities/
│   │   ├── page.tsx              # Activity list + filters
│   │   └── [id]/page.tsx         # Activity detail with lap/HR breakdown
│   ├── segments/page.tsx         # Segment performance trends
│   ├── race/
│   │   ├── predictor/page.tsx    # Race time predictions
│   │   └── retrospective/[id]/page.tsx
│   ├── gear/page.tsx             # Shoe mileage tracker
│   └── settings/
│       ├── page.tsx              # Settings hub
│       └── ai/page.tsx           # Gemini API key setup, model selector, theme picker
└── api/                          # Next.js API routes (proxy to FastAPI)
```

### Dashboard Home — Key Widgets

1. **Today's readiness card** — score (0–100), colour-coded, 3-bullet AI brief
2. **Next workout card** — type, distance/duration, target pace, weather conditions for that day
3. **This week at a glance** — planned vs completed workouts, weekly km progress bar
4. **HRV sparkline** — 14-day trend with baseline reference line
5. **Sleep sparkline** — 14-day sleep score trend
6. **Quick stats** — current CTL (fitness), ATL (fatigue), TSB (form)

### Charting

Use **Recharts** for all data visualisations:
- Line charts for HRV/sleep trends
- Area charts for ATL/CTL/TSB (PMC)
- Bar charts for weekly mileage
- Scatter plots for segment performance over time (x=date, y=elapsed_time, dot size=HR)

---

## Background Job Schedule (APScheduler)

```python
scheduler.add_job(sync_all_athletes_garmin_health, 'cron', hour=5, minute=0)   # 05:00 UTC
scheduler.add_job(compute_all_readiness_scores, 'cron', hour=5, minute=30)     # 05:30 UTC  
scheduler.add_job(send_morning_digests, 'cron', hour=6, minute=0)              # 06:00 UTC
scheduler.add_job(check_plan_revision_triggers, 'cron', hour=7, minute=0)      # 07:00 UTC
scheduler.add_job(update_gear_mileage, 'cron', hour=8, minute=0)               # 08:00 UTC
scheduler.add_job(refresh_strava_tokens, 'cron', hour=2, minute=0)             # 02:00 UTC (tokens expire every 6h)
```

---

## Build Phases

### Phase 1 — Data foundation (weeks 1–5)
- [ ] Neon database setup, run schema migrations
- [ ] Strava OAuth + webhook registration + backfill sync
- [ ] Garmin OAuth + activity + health API backfill
- [ ] Data normalisation pipeline
- [ ] Settings page: Gemini API key input, encrypt + store, test-connection endpoint
- [ ] `AIFeatureGate` component — onboarding banner when key not set
- [ ] Basic Next.js dashboard: activity list, weekly mileage, HRV/sleep charts

### Phase 2 — Health analyst (weeks 6–8)
- [ ] Daily readiness score computation
- [ ] Gemini API integration — daily brief prompt
- [ ] Morning digest delivery (email via Resend free tier)
- [ ] Health dashboard: readiness history, HRV trends, sleep analysis

### Phase 3 — Training planner (weeks 9–14)
- [ ] RAG setup: activity embeddings, coaching knowledge base
- [ ] Training plan generation with Gemini
- [ ] Adaptive revision engine (daily trigger check)
- [ ] Calendar export: Google Calendar + Garmin Training API + ICS
- [ ] Training calendar UI: week/month view, planned vs actual overlay

### Phase 4 — Advanced features (weeks 15–20)
- [ ] PMC chart (ATL/CTL/TSB)
- [ ] Race predictor (Riegel + AI analysis)
- [ ] Segment performance tracking + trend charts
- [ ] Dual weather source: Open-Meteo (temp/humidity) + MET Malaysia (rain warnings)
- [ ] Weather-adjusted pace display on training calendar
- [ ] Post-race retrospective (auto-triggered on race activity sync)
- [ ] Gear/shoe mileage tracker

---

## Strava AI Compliance Architecture

To comply with Strava's prohibition on using API data for AI:

1. Raw Strava API payloads are written to `activities.raw_metadata` (JSONB) and immediately discarded from memory
2. All downstream processing (AI prompts, embeddings, analysis) reads exclusively from the normalised `activities` table — never from `raw_metadata`
3. The AI layer has no import or dependency on `strava_client.py`
4. Document this in code comments at every boundary: `# Uses internal schema only — not Strava API data`

This satisfies the spirit of the policy: Strava data is used for display and sync; our own derived schema powers AI features.

---

## Cost Estimate (Personal Use, Monthly)

| Service | Cost |
|---|---|
| Neon (DB + pgvector + TimescaleDB) | $0 |
| Vercel (frontend) | $0 |
| Railway/Render (backend) | $0 (free tier) |
| Upstash Redis | $0 |
| Open-Meteo weather | $0 |
| MET Malaysia weather API | $0 |
| Strava API | $0 |
| Garmin API | $0 (personal use) |
| Google Calendar API | $0 |
| Gemini API (user's own free key) | $0 |
| Embeddings (sentence-transformers, local) | $0 |
| **Total** | **$0/month** |

---

## References

- Strava API docs: https://developers.strava.com/docs/
- Garmin Connect Developer Program: https://developer.garmin.com/gc-developer-program/
- Neon docs: https://neon.com/docs
- pgvector: https://github.com/pgvector/pgvector
- TimescaleDB: https://docs.timescale.com
- Open-Meteo: https://open-meteo.com/en/docs
- MET Malaysia open API: https://developer.data.gov.my/realtime-api/weather
- Google Gemini API docs: https://ai.google.dev/gemini-api/docs
- Gemini API rate limits: https://ai.google.dev/gemini-api/docs/rate-limits
- Google AI Studio (get API key): https://aistudio.google.com
- Riegel formula: https://en.wikipedia.org/wiki/Peter_Riegel
- Training Peaks PMC methodology: https://www.trainingpeaks.com/learn/articles/the-science-of-the-performance-manager/