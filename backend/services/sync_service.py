"""
Sync service — orchestrates data ingestion from Strava and Garmin.

Strava compliance: raw API responses go to raw_metadata and are not read by AI.
All AI/analysis reads from the normalised activities table only.
"""

import logging
from datetime import datetime, timedelta, timezone, date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from database import AsyncSessionLocal
from models.activity import Activity
from models.health import HealthMetrics
from models.gear import Gear

logger = logging.getLogger(__name__)


# ── Normalisation helpers ─────────────────────────────────────────────────────

def normalise_strava_activity(raw: dict, athlete_id: str) -> dict:
    """
    Map a Strava activity API response to the internal activities schema.
    # Uses internal schema only — not Strava API data (passed to AI layer)
    """
    started_at = datetime.strptime(raw["start_date"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    distance_m = raw.get("distance", 0)
    duration_s = raw.get("moving_time", 0)

    # Strava returns average_speed in m/s; convert to seconds/km
    avg_speed_mps = raw.get("average_speed", 0)
    avg_pace_s_per_km = (1000 / avg_speed_mps) if avg_speed_mps > 0 else None

    # Classify workout type from Strava workout_type field
    strava_workout_type = raw.get("workout_type", 0)
    workout_type_map = {0: None, 1: "race", 2: "long_run", 3: "interval", 10: "easy", 11: "tempo", 12: "interval"}
    workout_type = workout_type_map.get(strava_workout_type)

    # HR zone distribution — Strava doesn't provide this directly; computed later
    hr_zones = None

    # Per-km splits from laps
    splits = None
    if raw.get("splits_metric"):
        splits = [
            {
                "km": i + 1,
                "pace_s_per_km": int(s.get("moving_time", 0) / (s.get("distance", 1) / 1000)) if s.get("distance") else None,
                "hr": s.get("average_heartrate"),
                "elevation_diff": s.get("elevation_difference"),
            }
            for i, s in enumerate(raw["splits_metric"])
        ]

    return {
        "athlete_id": athlete_id,
        "source": "strava",
        "external_id": str(raw["id"]),
        "activity_type": raw.get("type", "run").lower(),
        "started_at": started_at,
        "duration_seconds": duration_s,
        "distance_meters": distance_m,
        "elevation_gain_meters": raw.get("total_elevation_gain"),
        "avg_hr": raw.get("average_heartrate"),
        "max_hr": raw.get("max_heartrate"),
        "avg_pace_seconds_per_km": avg_pace_s_per_km,
        "avg_cadence": int(raw["average_cadence"] * 2) if raw.get("average_cadence") else None,  # Strava gives one-foot cadence
        "avg_power": raw.get("average_watts"),
        "hr_zone_distribution": hr_zones,
        "splits": splits,
        "workout_type": workout_type,
        "perceived_effort": raw.get("perceived_exertion"),
        "notes": raw.get("description"),
        "gear_id": raw.get("gear_id"),
        "raw_metadata": raw,   # stored for debugging; AI layer never reads this
    }


# Garmin activityType.typeKey values that count as a run. Garmin splits running
# into many sub-types (treadmill, trail, track, virtual...).
GARMIN_RUN_TYPE_KEYS = {
    "running", "street_running", "treadmill_running", "trail_running",
    "track_running", "indoor_running", "virtual_run", "ultra_run", "obstacle_run",
}
GARMIN_RIDE_TYPE_KEYS = {
    "cycling", "road_biking", "mountain_biking", "gravel_cycling", "indoor_cycling",
    "virtual_ride", "e_bike_fitness", "e_bike_mountain", "cyclocross", "track_cycling",
}


def garmin_activity_type(type_key: str | None) -> str:
    """Map a Garmin typeKey to Stryde's activity_type ('run', 'ride', or the raw key)."""
    key = (type_key or "").lower()
    if key in GARMIN_RUN_TYPE_KEYS or key.endswith("_running"):
        return "run"
    if key in GARMIN_RIDE_TYPE_KEYS or key.endswith("_cycling"):
        return "ride"
    return key or "other"


def _parse_garmin_gmt(value: str | None) -> datetime | None:
    """Garmin startTimeGMT looks like '2026-10-18 22:12:03' (UTC, no zone marker)."""
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _garmin_hr_zones(raw: dict) -> dict | None:
    """Turn hrTimeInZone_1..5 (seconds) into fractions {z1: 0.15, ...}."""
    seconds = {f"z{i}": raw.get(f"hrTimeInZone_{i}") for i in range(1, 6)}
    if all(v is None for v in seconds.values()):
        return None
    total = sum(v or 0 for v in seconds.values())
    if total <= 0:
        return None
    return {k: round((v or 0) / total, 3) for k, v in seconds.items()}


def normalise_garmin_activity(raw: dict, athlete_id: str) -> dict:
    """
    Map a Garmin Connect activity summary (garminconnect get_activities_by_date)
    to the internal activities schema.
    """
    started_at = _parse_garmin_gmt(raw.get("startTimeGMT"))
    if started_at is None:
        raise ValueError(f"Garmin activity {raw.get('activityId')} has no usable startTimeGMT")

    distance_m = raw.get("distance") or 0
    duration_s = raw.get("movingDuration") or raw.get("duration") or 0

    avg_speed_mps = raw.get("averageSpeed") or 0
    if avg_speed_mps > 0:
        avg_pace_s_per_km = 1000 / avg_speed_mps
    elif distance_m > 0 and duration_s > 0:
        avg_pace_s_per_km = duration_s / (distance_m / 1000)
    else:
        avg_pace_s_per_km = None

    cadence = raw.get("averageRunningCadenceInStepsPerMinute")
    avg_hr = raw.get("averageHR")
    max_hr = raw.get("maxHR")
    avg_power = raw.get("avgPower")

    return {
        "athlete_id": athlete_id,
        "source": "garmin",
        "external_id": str(raw["activityId"]),
        "activity_type": garmin_activity_type((raw.get("activityType") or {}).get("typeKey")),
        "started_at": started_at,
        "duration_seconds": int(duration_s) if duration_s else None,
        "distance_meters": float(distance_m) if distance_m else None,
        "elevation_gain_meters": raw.get("elevationGain"),
        "avg_hr": int(round(avg_hr)) if avg_hr is not None else None,
        "max_hr": int(round(max_hr)) if max_hr is not None else None,
        "avg_pace_seconds_per_km": avg_pace_s_per_km,
        "avg_cadence": int(round(cadence)) if cadence is not None else None,  # already steps/min, both feet
        "avg_power": int(round(avg_power)) if avg_power is not None else None,
        "hr_zone_distribution": _garmin_hr_zones(raw),
        "splits": None,
        "workout_type": None,
        "perceived_effort": None,
        "notes": raw.get("description"),
        "gear_id": None,
        "raw_metadata": raw,
    }


def normalise_garmin_health_connect(raw: dict, for_date: date, athlete_id: str) -> dict:
    """
    Map python-garminconnect health data to health_metrics schema.
    raw = {stats, sleep, hrv, rhr} from garmin_client.fetch_health_day()
    # Uses internal schema only — not Garmin API data (passed to AI layer)
    """
    stats = raw.get("stats") or {}
    sleep_raw = raw.get("sleep") or {}
    hrv_raw = raw.get("hrv") or {}
    rhr_raw = raw.get("rhr") or {}

    # Sleep — nested under dailySleepDTO
    sleep_dto = sleep_raw.get("dailySleepDTO") or {}
    sleep_duration = (sleep_dto.get("sleepTimeSeconds") or 0) // 60 or None
    deep_sleep = (sleep_dto.get("deepSleepSeconds") or 0) // 60 or None
    light_sleep = (sleep_dto.get("lightSleepSeconds") or 0) // 60 or None
    rem_sleep = (sleep_dto.get("remSleepSeconds") or 0) // 60 or None
    awake_count = sleep_dto.get("awakeCount")
    sleep_stress_avg = sleep_dto.get("avgSleepStress")
    sleep_score_insight = sleep_dto.get("sleepScoreInsight")  # e.g. "NEGATIVE_LATE_BED_TIME"
    sleep_start = None
    sleep_end = None
    if sleep_dto.get("sleepStartTimestampGMT"):
        sleep_start = datetime.fromtimestamp(sleep_dto["sleepStartTimestampGMT"] / 1000, tz=timezone.utc)
    if sleep_dto.get("sleepEndTimestampGMT"):
        sleep_end = datetime.fromtimestamp(sleep_dto["sleepEndTimestampGMT"] / 1000, tz=timezone.utc)
    # sleepScores is inside dailySleepDTO, overall.value is the score
    sleep_score = (sleep_dto.get("sleepScores") or {}).get("overall", {}).get("value")

    # HRV — nested under hrvSummary
    hrv_summary = hrv_raw.get("hrvSummary") or {}
    hrv_rmssd = hrv_summary.get("lastNight") or hrv_summary.get("rmssd")
    hrv_sdrr = hrv_summary.get("sdrr")

    # Resting HR
    resting_hr = (
        stats.get("restingHeartRate")
        or rhr_raw.get("value")
        or (rhr_raw.get("allMetrics", {}).get("metricsMap", {}).get("WELLNESS_RESTING_HEART_RATE") or [{}])[0].get("value")
    )
    if isinstance(resting_hr, float):
        resting_hr = int(resting_hr)

    # Body battery — flat fields in stats (not a nested dict)
    bb_max = stats.get("bodyBatteryChargedValue") or stats.get("bodyBatteryHighestValue")
    bb_min = stats.get("bodyBatteryDrainedValue") or stats.get("bodyBatteryLowestValue")
    bb_at_wake = stats.get("bodyBatteryAtWakeTime")

    return {
        "athlete_id": athlete_id,
        "recorded_date": for_date,
        "hrv_rmssd": float(hrv_rmssd) if hrv_rmssd is not None else None,
        "hrv_sdrr": float(hrv_sdrr) if hrv_sdrr is not None else None,
        "resting_hr": resting_hr,
        "sleep_score": int(sleep_score) if sleep_score is not None else None,
        "sleep_duration_minutes": sleep_duration,
        "deep_sleep_minutes": deep_sleep,
        "light_sleep_minutes": light_sleep,
        "rem_sleep_minutes": rem_sleep,
        "awake_count": int(awake_count) if awake_count is not None else None,
        "sleep_stress_avg": float(sleep_stress_avg) if sleep_stress_avg is not None else None,
        "sleep_score_insight": sleep_score_insight,
        "sleep_start": sleep_start,
        "sleep_end": sleep_end,
        "body_battery_max": int(bb_max) if bb_max is not None else None,
        "body_battery_min": int(bb_min) if bb_min is not None else None,
        "body_battery_at_wake": int(bb_at_wake) if bb_at_wake is not None else None,
        "stress_avg": stats.get("averageStressLevel"),
        "steps": stats.get("totalSteps"),
        "spo2_avg": stats.get("averageSpo2"),
        "respiratory_rate": stats.get("avgWakingRespirationValue") or stats.get("averageRespiratoryRate"),
        "training_readiness_score": stats.get("trainingReadinessScore"),
    }


# ── Upsert helpers ────────────────────────────────────────────────────────────

async def upsert_activity(data: dict, db) -> str:
    """Insert or update an activity. Returns the activity ID."""
    import uuid

    stmt = (
        insert(Activity.__table__)
        .values(id=str(uuid.uuid4()), **data)
        .on_conflict_do_update(
            index_elements=["source", "external_id"],
            set_={k: v for k, v in data.items() if k not in ("source", "external_id", "athlete_id")},
        )
        .returning(Activity.__table__.c.id)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.scalar_one()


async def upsert_health_metrics(data: dict, db) -> None:
    """Insert or update a health_metrics row."""
    stmt = (
        insert(HealthMetrics.__table__)
        .values(**data)
        .on_conflict_do_update(
            index_elements=["athlete_id", "recorded_date"],
            set_={k: v for k, v in data.items() if k not in ("athlete_id", "recorded_date")},
        )
    )
    await db.execute(stmt)
    await db.commit()


# ── Sync functions ────────────────────────────────────────────────────────────

async def sync_single_strava_activity(strava_owner_id: str, activity_id: int) -> None:
    """Called by webhook when a new Strava activity is created. No-op while Strava is switched off."""
    from config import settings
    if not settings.STRAVA_ENABLED:
        return
    from models.athlete import Athlete
    from services.strava_client import get_valid_strava_client

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Athlete).where(Athlete.strava_athlete_id == int(strava_owner_id))
        )
        athlete = result.scalar_one_or_none()
        if not athlete:
            logger.warning(f"No athlete found for Strava owner_id={strava_owner_id}")
            return

        client = await get_valid_strava_client(str(athlete.id), db)
        if not client:
            return

        try:
            raw = await client.get_activity(activity_id)
            data = normalise_strava_activity(raw, str(athlete.id))
            await upsert_activity(data, db)
            logger.info(f"Synced Strava activity {activity_id} for athlete {athlete.id}")
        finally:
            await client.close()


async def trigger_strava_backfill(athlete_id: str) -> None:
    """Backfill last 90 days of Strava activities. No-op while Strava is switched off."""
    from config import settings
    if not settings.STRAVA_ENABLED:
        return
    from services.strava_client import get_valid_strava_client
    import time

    after_ts = int((datetime.now(timezone.utc) - timedelta(days=90)).timestamp())

    async with AsyncSessionLocal() as db:
        client = await get_valid_strava_client(athlete_id, db)
        if not client:
            return

        try:
            page = 1
            total = 0
            while True:
                activities = await client.list_activities(after=after_ts, per_page=50, page=page)
                if not activities:
                    break
                for raw in activities:
                    # Only backfill runs
                    if raw.get("type", "").lower() != "run":
                        continue
                    # Fetch full detail for splits/HR zones
                    try:
                        detail = await client.get_activity(raw["id"])
                        data = normalise_strava_activity(detail, athlete_id)
                        await upsert_activity(data, db)
                        total += 1
                    except Exception as e:
                        logger.error(f"Failed to sync activity {raw['id']}: {e}")

                page += 1

            logger.info(f"Strava backfill complete for {athlete_id}: {total} activities")
        finally:
            await client.close()


# ── Garmin sync ───────────────────────────────────────────────────────────────

GARMIN_BACKFILL_HEALTH_DAYS = 90
GARMIN_BACKFILL_ACTIVITY_DAYS = 365
GARMIN_DAILY_HEALTH_DAYS = 3      # re-fetch a few days: Garmin fills sleep/HRV in late
GARMIN_DAILY_ACTIVITY_DAYS = 7


def athlete_today() -> date:
    """Today in the athlete's timezone (the server runs on UTC)."""
    from zoneinfo import ZoneInfo
    from config import settings
    return datetime.now(ZoneInfo(settings.ATHLETE_TIMEZONE)).date()


async def sync_garmin_health(athlete_id: str, days: int, db) -> int:
    """Fetch and store health metrics for the last `days` days (including today)."""
    from services.garmin_client import get_valid_garmin_tokens, fetch_health_range, save_refreshed_tokens

    tokens_json = await get_valid_garmin_tokens(athlete_id, db)
    if not tokens_json:
        logger.debug(f"Garmin health sync skipped for {athlete_id} — not connected")
        return 0

    end = athlete_today()
    start = end - timedelta(days=days - 1)
    by_date, refreshed = await fetch_health_range(tokens_json, start, end)

    stored = 0
    for day, raw in sorted(by_date.items()):
        data = normalise_garmin_health_connect(raw, day, athlete_id)
        if any(v is not None for k, v in data.items() if k not in ("athlete_id", "recorded_date")):
            await upsert_health_metrics(data, db)
            stored += 1

    if refreshed and refreshed != tokens_json:
        await save_refreshed_tokens(athlete_id, refreshed, db)
    logger.info(f"Garmin health sync for {athlete_id}: {stored}/{len(by_date)} days with data")
    return stored


async def sync_garmin_activities(athlete_id: str, days: int, db) -> int:
    """Fetch and store Garmin activities started in the last `days` days."""
    from services.garmin_client import get_valid_garmin_tokens, fetch_activities, save_refreshed_tokens

    tokens_json = await get_valid_garmin_tokens(athlete_id, db)
    if not tokens_json:
        logger.debug(f"Garmin activity sync skipped for {athlete_id} — not connected")
        return 0

    end = athlete_today()
    start = end - timedelta(days=days - 1)
    activities, refreshed = await fetch_activities(tokens_json, start, end)

    stored = 0
    for raw in activities:
        try:
            await upsert_activity(normalise_garmin_activity(raw, athlete_id), db)
            stored += 1
        except Exception as e:
            logger.error(f"Failed to store Garmin activity {raw.get('activityId')}: {e}")

    if refreshed and refreshed != tokens_json:
        await save_refreshed_tokens(athlete_id, refreshed, db)
    logger.info(f"Garmin activity sync for {athlete_id}: {stored}/{len(activities)} activities stored")
    return stored


async def trigger_garmin_backfill(athlete_id: str) -> None:
    """Full backfill after connecting or a manual sync: 90 days of health, a year of activities."""
    async with AsyncSessionLocal() as db:
        await sync_garmin_activities(athlete_id, GARMIN_BACKFILL_ACTIVITY_DAYS, db)
        await sync_garmin_health(athlete_id, GARMIN_BACKFILL_HEALTH_DAYS, db)


async def trigger_garmin_daily_sync(athlete_id: str) -> None:
    """Light nightly sync: last few days of health and last week of activities."""
    async with AsyncSessionLocal() as db:
        await sync_garmin_activities(athlete_id, GARMIN_DAILY_ACTIVITY_DAYS, db)
        await sync_garmin_health(athlete_id, GARMIN_DAILY_HEALTH_DAYS, db)


# ── Strava removal ────────────────────────────────────────────────────────────

async def delete_strava_data(athlete_id: str, db) -> int:
    """Delete Strava-sourced activities and the stored Strava token. Returns activities deleted."""
    from sqlalchemy import delete
    from models.oauth import OAuthToken

    result = await db.execute(
        delete(Activity).where(Activity.athlete_id == athlete_id, Activity.source == "strava")
    )
    await db.execute(
        delete(OAuthToken).where(OAuthToken.athlete_id == athlete_id, OAuthToken.provider == "strava")
    )
    await db.commit()
    return result.rowcount or 0
