"""
AI service — generates daily readiness brief using Gemini.
# Uses internal schema only — not Strava API data
"""
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.activity import Activity
from models.athlete import Athlete
from models.health import ReadinessScore
from utils.encryption import decrypt_api_key
from utils.pace import meters_to_km, seconds_per_km_to_min_km

logger = logging.getLogger(__name__)


async def generate_daily_brief(
    athlete_id: str,
    for_date: date,
    db: AsyncSession,
    redis,
) -> str | None:
    """
    Generate and store the daily AI brief for the given athlete and date.
    Returns the brief text, or None if Gemini not configured / quota exceeded.
    # Uses internal schema only — not Strava API data
    """
    from services.rate_limiter import check_and_increment_quota
    from services.gemini_client import call_gemini
    from services.readiness_service import compute_and_store_readiness
    from prompts.daily_brief import build_daily_brief_prompt

    result = await db.execute(select(Athlete).where(Athlete.id == athlete_id))
    athlete = result.scalar_one_or_none()
    if not athlete or not athlete.gemini_api_key_encrypted:
        return None

    allowed = await check_and_increment_quota(athlete_id, redis)
    if not allowed:
        logger.warning(f"Gemini daily quota exceeded for athlete {athlete_id}")
        return None

    readiness = await compute_and_store_readiness(athlete_id, for_date, db)
    if not readiness:
        logger.debug(f"No readiness data for {athlete_id} on {for_date} — skipping brief")
        return None

    # Fetch last 7 days of runs — internal schema only
    seven_ago_dt = datetime.combine(for_date - timedelta(days=7), datetime.min.time()).replace(tzinfo=timezone.utc)
    result = await db.execute(
        select(Activity).where(
            Activity.athlete_id == athlete_id,
            Activity.activity_type == "run",
            Activity.started_at >= seven_ago_dt,
        ).order_by(Activity.started_at)
    )
    activities = result.scalars().all()
    act_dicts = [
        {
            "started_at": a.started_at.isoformat(),
            "distance_km": round(meters_to_km(a.distance_meters or 0), 1),
            "pace_str": seconds_per_km_to_min_km(a.avg_pace_seconds_per_km) if a.avg_pace_seconds_per_km else None,
            "avg_hr": a.avg_hr,
            "workout_type": a.workout_type,
        }
        for a in activities
    ]

    goal_date = None
    if athlete.goal_race_date:
        goal_date = athlete.goal_race_date if isinstance(athlete.goal_race_date, date) else athlete.goal_race_date.date()

    prompt = build_daily_brief_prompt(
        athlete_name=athlete.name,
        for_date=for_date,
        readiness_score=readiness.readiness_score or 75.0,
        hrv_delta=readiness.hrv_delta_pct,
        sleep_delta=readiness.sleep_delta_pct,
        load_delta=readiness.load_delta_pct,
        recent_activities=act_dicts,
        goal_race_type=athlete.goal_race_type,
        goal_race_date=goal_date,
        goal_finish_time_seconds=athlete.goal_finish_time_seconds,
    )

    try:
        api_key = decrypt_api_key(athlete.gemini_api_key_encrypted)
        brief = await call_gemini(
            prompt=prompt,
            api_key=api_key,
            model=athlete.gemini_model,
        )
    except ValueError as exc:
        logger.error(f"Gemini auth error for athlete {athlete_id}: {exc}")
        return None
    except RuntimeError as exc:
        logger.warning(f"Gemini rate limit for athlete {athlete_id}: {exc}")
        return None
    except Exception as exc:
        logger.error(f"Gemini unexpected error for athlete {athlete_id}: {exc}")
        return None

    # Store brief on the readiness row
    readiness.ai_summary = brief
    await db.commit()

    logger.info(f"Daily brief generated for athlete {athlete_id} on {for_date}")
    return brief
