"""
Redis-backed daily quota counter for Gemini API calls.
Key: gemini:quota:{athlete_id}:{YYYY-MM-DD}  (TTL 48h)
"""
import logging
from datetime import date

logger = logging.getLogger(__name__)

GEMINI_DAILY_LIMIT = 50


async def check_and_increment_quota(athlete_id: str, redis) -> bool:
    """
    Increment today's Gemini call counter for this athlete.
    Returns True if the call is allowed, False if quota exceeded.
    """
    key = f"gemini:quota:{athlete_id}:{date.today().isoformat()}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 48 * 3600)
    if count > GEMINI_DAILY_LIMIT:
        logger.warning(f"Gemini daily quota exceeded for athlete {athlete_id}: {count}/{GEMINI_DAILY_LIMIT}")
        return False
    return True


async def get_daily_usage(athlete_id: str, redis) -> int:
    """Return current daily Gemini call count for this athlete."""
    key = f"gemini:quota:{athlete_id}:{date.today().isoformat()}"
    count = await redis.get(key)
    return int(count) if count else 0
