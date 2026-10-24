"""
Cron router — lets an external scheduler run the daily jobs.

On Vercel nothing runs between requests, so APScheduler is off.
.github/workflows/daily-jobs.yml calls POST /cron/daily every morning instead.
"""
import asyncio
import hmac
import logging
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException

from config import settings
from services.scheduler import run_daily_jobs
from utils.background import run_after_response

logger = logging.getLogger(__name__)

router = APIRouter()

_daily_lock = asyncio.Lock()


async def _run_daily_locked():
    async with _daily_lock:
        await run_daily_jobs()


@router.post("/daily")
async def run_daily(x_cron_secret: Annotated[str | None, Header()] = None):
    # Endpoint is invisible unless CRON_SECRET is configured
    if not settings.CRON_SECRET:
        raise HTTPException(status_code=404, detail="Not found")
    if not x_cron_secret or not hmac.compare_digest(x_cron_secret, settings.CRON_SECRET):
        raise HTTPException(status_code=401, detail="Invalid cron secret")
    if _daily_lock.locked():
        return {"status": "already running"}

    # Inline on Vercel (request waits until the jobs finish), background elsewhere
    await run_after_response(_run_daily_locked())
    return {"status": "done" if settings.VERCEL else "started"}
