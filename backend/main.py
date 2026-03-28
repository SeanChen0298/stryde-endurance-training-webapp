import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if not settings.GARMIN_CLIENT_ID:
        logger.warning("Garmin credentials not configured — sync disabled")

    from services.scheduler import start_scheduler
    start_scheduler()

    yield

    # Shutdown
    from services.scheduler import stop_scheduler
    stop_scheduler()


app = FastAPI(
    title="Stryde Endurance Training API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Exception handlers ────────────────────────────────────────────────────────

class GeminiDailyLimitReached(Exception):
    pass


@app.exception_handler(GeminiDailyLimitReached)
async def gemini_limit_handler(request: Request, exc: GeminiDailyLimitReached):
    return JSONResponse(
        status_code=503,
        content={"error": "AI quota reached", "code": "AI_QUOTA", "detail": str(exc)},
    )


@app.exception_handler(httpx.HTTPStatusError)
async def external_api_handler(request: Request, exc: httpx.HTTPStatusError):
    return JSONResponse(
        status_code=502,
        content={"error": "External API error", "detail": str(exc)},
    )


# ── Routers ───────────────────────────────────────────────────────────────────

from routers import auth, activities, dashboard, settings as settings_router

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(activities.router, prefix="/activities", tags=["activities"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
app.include_router(settings_router.router, prefix="/settings", tags=["settings"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}
