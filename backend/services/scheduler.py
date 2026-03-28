"""
APScheduler job definitions for background tasks.

Phase 1 jobs:
- Daily Garmin health sync (06:00 MYT)

Phase 2+ jobs (stubs, activated when AI is configured):
- Daily readiness brief generation (06:05 MYT)
- Plan revision check (07:00 MYT)
"""

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def start_scheduler():
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone="Asia/Kuala_Lumpur")

    # Phase 1: nightly Garmin health data sync at 06:00 MYT
    _scheduler.add_job(
        _daily_garmin_sync,
        CronTrigger(hour=6, minute=0),
        id="daily_garmin_sync",
        replace_existing=True,
    )

    # Phase 2: daily readiness brief at 06:05 MYT
    _scheduler.add_job(
        _daily_readiness_brief,
        CronTrigger(hour=6, minute=5),
        id="daily_readiness_brief",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("APScheduler started")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")


async def _daily_readiness_brief():
    """Generate daily AI brief for all athletes with Gemini configured."""
    from datetime import date as date_type

    from database import AsyncSessionLocal
    from models.athlete import Athlete
    from services.ai_service import generate_daily_brief
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Athlete.id).where(Athlete.gemini_api_key_encrypted.is_not(None))
        )
        athlete_ids = [row[0] for row in result.fetchall()]

    import redis.asyncio as aioredis
    from config import settings as cfg

    today = date_type.today()
    redis = await aioredis.from_url(cfg.REDIS_URL, decode_responses=True)
    try:
        for athlete_id in athlete_ids:
            async with AsyncSessionLocal() as db:
                try:
                    await generate_daily_brief(athlete_id, today, db, redis)
                except Exception as exc:
                    logger.error(f"Daily brief failed for athlete {athlete_id}: {exc}")
    finally:
        await redis.aclose()


async def _daily_garmin_sync():
    """Sync Garmin health data for all athletes with Garmin credentials stored."""
    from database import AsyncSessionLocal
    from models.athlete import Athlete
    from services.sync_service import trigger_garmin_backfill
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Athlete.id).where(Athlete.garmin_tokens_encrypted.is_not(None))
        )
        athlete_ids = [row[0] for row in result.fetchall()]

    for athlete_id in athlete_ids:
        try:
            await trigger_garmin_backfill(athlete_id)
        except Exception as e:
            logger.error(f"Garmin sync failed for athlete {athlete_id}: {e}")
