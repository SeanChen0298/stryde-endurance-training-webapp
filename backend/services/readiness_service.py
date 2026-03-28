"""
Compute and store daily readiness scores from health + activity data.
"""
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.activity import Activity
from models.health import HealthMetrics, ReadinessScore
from utils.hrv import compute_hrv_baseline, hrv_delta_pct, compute_readiness_score, readiness_to_label

logger = logging.getLogger(__name__)


async def compute_and_store_readiness(
    athlete_id: str,
    for_date: date,
    db: AsyncSession,
) -> ReadinessScore | None:
    """
    Compute readiness score for the given date and upsert into readiness_scores.
    Returns None if no health metrics exist for that date.
    """
    # Today's health metrics
    result = await db.execute(
        select(HealthMetrics).where(
            HealthMetrics.athlete_id == athlete_id,
            HealthMetrics.recorded_date == for_date,
        )
    )
    today_hm = result.scalar_one_or_none()
    if not today_hm:
        logger.debug(f"No health metrics for athlete {athlete_id} on {for_date} — skipping readiness")
        return None

    # ── HRV delta vs 30-day baseline ──────────────────────────────────────────
    hrv_delta = None
    if today_hm.hrv_rmssd is not None:
        thirty_ago = for_date - timedelta(days=30)
        result = await db.execute(
            select(HealthMetrics.hrv_rmssd).where(
                HealthMetrics.athlete_id == athlete_id,
                HealthMetrics.recorded_date >= thirty_ago,
                HealthMetrics.recorded_date < for_date,
                HealthMetrics.hrv_rmssd.is_not(None),
            ).order_by(HealthMetrics.recorded_date)
        )
        hrv_history = [row[0] for row in result.fetchall()]
        if hrv_history:
            baseline = compute_hrv_baseline(hrv_history)
            if baseline["mean"]:
                hrv_delta = hrv_delta_pct(today_hm.hrv_rmssd, baseline["mean"])

    # ── Sleep delta vs 7-day avg ───────────────────────────────────────────────
    sleep_delta = None
    if today_hm.sleep_score is not None:
        seven_ago = for_date - timedelta(days=7)
        result = await db.execute(
            select(HealthMetrics.sleep_score).where(
                HealthMetrics.athlete_id == athlete_id,
                HealthMetrics.recorded_date >= seven_ago,
                HealthMetrics.recorded_date < for_date,
                HealthMetrics.sleep_score.is_not(None),
            )
        )
        sleep_history = [row[0] for row in result.fetchall()]
        if sleep_history:
            avg = sum(sleep_history) / len(sleep_history)
            if avg:
                sleep_delta = round((today_hm.sleep_score - avg) / avg * 100, 1)

    # ── Resting HR delta vs 30-day baseline ───────────────────────────────────
    hr_delta = None
    if today_hm.resting_hr is not None:
        thirty_ago = for_date - timedelta(days=30)
        result = await db.execute(
            select(HealthMetrics.resting_hr).where(
                HealthMetrics.athlete_id == athlete_id,
                HealthMetrics.recorded_date >= thirty_ago,
                HealthMetrics.recorded_date < for_date,
                HealthMetrics.resting_hr.is_not(None),
            )
        )
        hr_history = [row[0] for row in result.fetchall()]
        if hr_history:
            avg = sum(hr_history) / len(hr_history)
            if avg:
                hr_delta = round((today_hm.resting_hr - avg) / avg * 100, 1)

    # ── Training load: yesterday km vs 7-day avg ───────────────────────────────
    load_delta = None
    seven_ago_dt = datetime.combine(for_date - timedelta(days=7), datetime.min.time()).replace(tzinfo=timezone.utc)
    result = await db.execute(
        select(Activity).where(
            Activity.athlete_id == athlete_id,
            Activity.activity_type == "run",
            Activity.started_at >= seven_ago_dt,
        )
    )
    recent = result.scalars().all()
    if recent:
        weekly_km = sum((a.distance_meters or 0) / 1000 for a in recent)
        avg_daily_km = weekly_km / 7
        yesterday = for_date - timedelta(days=1)
        yesterday_km = sum(
            (a.distance_meters or 0) / 1000
            for a in recent
            if a.started_at.date() == yesterday
        )
        if avg_daily_km > 0:
            load_delta = round((yesterday_km - avg_daily_km) / avg_daily_km * 100, 1)

    score = compute_readiness_score(hrv_delta, sleep_delta, hr_delta, load_delta)

    # Upsert
    stmt = (
        insert(ReadinessScore.__table__)
        .values(
            athlete_id=athlete_id,
            score_date=for_date,
            readiness_score=score,
            hrv_delta_pct=hrv_delta,
            sleep_delta_pct=sleep_delta,
            load_delta_pct=load_delta,
        )
        .on_conflict_do_update(
            index_elements=["athlete_id", "score_date"],
            set_={
                "readiness_score": score,
                "hrv_delta_pct": hrv_delta,
                "sleep_delta_pct": sleep_delta,
                "load_delta_pct": load_delta,
            },
        )
    )
    await db.execute(stmt)
    await db.commit()

    result = await db.execute(
        select(ReadinessScore).where(
            ReadinessScore.athlete_id == athlete_id,
            ReadinessScore.score_date == for_date,
        )
    )
    return result.scalar_one_or_none()
