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


def normalise_garmin_activity(raw: dict, athlete_id: str) -> dict:
    """
    Map a Garmin activity to the internal activities schema.
    # Uses internal schema only — not Garmin API data (passed to AI layer)
    """
    start_ts = raw.get("startTimeInSeconds", 0)
    started_at = datetime.fromtimestamp(start_ts, tz=timezone.utc)

    distance_m = raw.get("distanceInMeters", 0)
    duration_s = raw.get("durationInSeconds", 0)
    avg_pace_s_per_km = (duration_s / (distance_m / 1000)) if distance_m > 0 else None

    return {
        "athlete_id": athlete_id,
        "source": "garmin",
        "external_id": str(raw.get("activityId", "")),
        "activity_type": raw.get("activityType", "running").lower().replace("running", "run"),
        "started_at": started_at,
        "duration_seconds": duration_s,
        "distance_meters": distance_m,
        "elevation_gain_meters": raw.get("totalElevationGainInMeters"),
        "avg_hr": raw.get("averageHeartRateInBeatsPerMinute"),
        "max_hr": raw.get("maxHeartRateInBeatsPerMinute"),
        "avg_pace_seconds_per_km": avg_pace_s_per_km,
        "avg_cadence": raw.get("averageRunCadenceInStepsPerMinute"),
        "avg_power": raw.get("averagePowerInWatts"),
        "hr_zone_distribution": None,
        "splits": None,
        "workout_type": None,
        "perceived_effort": None,
        "notes": raw.get("description"),
        "gear_id": None,
        "raw_metadata": raw,
    }


def normalise_garmin_health(raw_daily: dict, raw_sleep: dict | None, raw_hrv: dict | None, athlete_id: str) -> dict:
    """
    Map Garmin wellness + sleep + HRV data to health_metrics schema.
    """
    cal_date = raw_daily.get("calendarDate")
    recorded_date = datetime.strptime(cal_date, "%Y-%m-%d").date() if cal_date else None

    sleep_duration = None
    deep_sleep = None
    rem_sleep = None
    sleep_start = None
    sleep_end = None
    sleep_score = None

    if raw_sleep:
        sleep_duration = raw_sleep.get("sleepTimeSeconds", 0) // 60
        deep_sleep = raw_sleep.get("deepSleepDurationInSeconds", 0) // 60
        rem_sleep = raw_sleep.get("remSleepInSeconds", 0) // 60
        sleep_score = raw_sleep.get("sleepScores", {}).get("overall", {}).get("value")

        if raw_sleep.get("startTimeInSeconds"):
            sleep_start = datetime.fromtimestamp(raw_sleep["startTimeInSeconds"], tz=timezone.utc)
        if raw_sleep.get("endTimeInSeconds"):
            sleep_end = datetime.fromtimestamp(raw_sleep["endTimeInSeconds"], tz=timezone.utc)

    hrv_rmssd = None
    hrv_sdrr = None
    if raw_hrv:
        hrv_rmssd = raw_hrv.get("lastNight", {}).get("rmssd")
        hrv_sdrr = raw_hrv.get("lastNight", {}).get("sdrr")

    return {
        "athlete_id": athlete_id,
        "recorded_date": recorded_date,
        "hrv_rmssd": hrv_rmssd,
        "hrv_sdrr": hrv_sdrr,
        "resting_hr": raw_daily.get("restingHeartRateInBeatsPerMinute"),
        "sleep_score": sleep_score,
        "sleep_duration_minutes": sleep_duration,
        "deep_sleep_minutes": deep_sleep,
        "rem_sleep_minutes": rem_sleep,
        "sleep_start": sleep_start,
        "sleep_end": sleep_end,
        "body_battery_max": raw_daily.get("bodyBatteryMostRecentValue"),
        "body_battery_min": raw_daily.get("bodyBatteryLowestValue"),
        "stress_avg": raw_daily.get("averageStressLevel"),
        "steps": raw_daily.get("totalSteps"),
        "spo2_avg": raw_daily.get("averageSpo2"),
        "respiratory_rate": raw_daily.get("averageRespiratoryRate"),
        "training_readiness_score": raw_daily.get("trainingReadinessScore"),
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
    """Called by webhook when a new Strava activity is created."""
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
    """Backfill last 90 days of Strava activities for a newly connected athlete."""
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


async def trigger_garmin_backfill(athlete_id: str) -> None:
    """Backfill 90 days of Garmin health data. Silently skips if creds not configured."""
    from config import settings
    from services.garmin_client import get_valid_garmin_client

    if not settings.GARMIN_CLIENT_ID:
        logger.debug("Garmin backfill skipped — credentials not configured")
        return

    start = date.today() - timedelta(days=90)
    end = date.today()

    async with AsyncSessionLocal() as db:
        client = await get_valid_garmin_client(athlete_id, db)
        if not client:
            return

        try:
            dailies = await client.get_daily_summaries(start, end)
            sleeps = {s["calendarDate"]: s for s in await client.get_sleep_data(start, end)}
            hrvs = {h.get("calendarDate", ""): h for h in await client.get_hrv_data(start, end)}

            for daily in dailies:
                cal_date = daily.get("calendarDate", "")
                data = normalise_garmin_health(
                    daily,
                    sleeps.get(cal_date),
                    hrvs.get(cal_date),
                    athlete_id,
                )
                if data.get("recorded_date"):
                    await upsert_health_metrics(data, db)

            logger.info(f"Garmin health backfill complete for {athlete_id}: {len(dailies)} days")
        finally:
            await client.close()
