"""
Cron router — lets an external scheduler run the daily jobs.

On Render's free tier the instance sleeps when idle, so APScheduler can't be
relied on. .github/workflows/daily-jobs.yml wakes the backend and calls
POST /cron/daily every morning instead.
"""
import asyncio
import hmac
import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException

from config import settings
from services.scheduler import run_daily_jobs

logger = logging.getLogger(__name__)

router = APIRouter()

_daily_lock = asyncio.Lock()


async def _run_daily_locked():
    async with _daily_lock:
        await run_daily_jobs()


@router.post("/daily", status_code=202)
async def run_daily(
    background_tasks: BackgroundTasks,
    x_cron_secret: Annotated[str | None, Header()] = None,
):
    # Endpoint is invisible unless CRON_SECRET is configured
    if not settings.CRON_SECRET:
        raise HTTPException(status_code=404, detail="Not found")
    if not x_cron_secret or not hmac.compare_digest(x_cron_secret, settings.CRON_SECRET):
        raise HTTPException(status_code=401, detail="Invalid cron secret")
    if _daily_lock.locked():
        return {"status": "already running"}

    background_tasks.add_task(_run_daily_locked)
    return {"status": "started"}
