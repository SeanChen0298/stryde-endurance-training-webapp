"""
Health router — readiness scores and health metrics history.
# Uses internal schema only — not Strava API data
"""
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from dependencies import get_current_athlete
from models.athlete import Athlete
from models.health import HealthMetrics, ReadinessScore
from utils.hrv import readiness_to_label

router = APIRouter()


class ReadinessPoint(BaseModel):
    date: str
    score: float | None
    label: str | None
    ai_summary: str | None


class HealthDayDetail(BaseModel):
    date: str
    readiness_score: float | None
    readiness_label: str | None
    hrv_delta_pct: float | None
    sleep_delta_pct: float | None
    load_delta_pct: float | None
    ai_summary: str | None
    ai_recommendation: str | None
    hrv_rmssd: float | None
    resting_hr: int | None
    sleep_score: int | None
    sleep_score_insight: str | None
    sleep_duration_minutes: int | None
    deep_sleep_minutes: int | None
    light_sleep_minutes: int | None
    rem_sleep_minutes: int | None
    awake_count: int | None
    sleep_stress_avg: float | None
    body_battery_max: int | None
    body_battery_min: int | None
    body_battery_at_wake: int | None
    stress_avg: int | None
    steps: int | None
    spo2_avg: float | None


@router.get("/history", response_model=list[ReadinessPoint])
async def get_health_history(
    athlete: Annotated[Athlete, Depends(get_current_athlete)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = 30,
):
    """Return readiness score history for the last N days (max 90)."""
    days = min(days, 90)
    since = date.today() - timedelta(days=days)
    result = await db.execute(
        select(ReadinessScore).where(
            ReadinessScore.athlete_id == athlete.id,
            ReadinessScore.score_date >= since,
        ).order_by(ReadinessScore.score_date)
    )
    by_date = {str(r.score_date): r for r in result.scalars().all()}

    points = []
    for i in range(days):
        d = str(date.today() - timedelta(days=days - 1 - i))
        r = by_date.get(d)
        label = readiness_to_label(r.readiness_score)[0] if r and r.readiness_score else None
        points.append(ReadinessPoint(
            date=d,
            score=r.readiness_score if r else None,
            label=label,
            ai_summary=r.ai_summary if r else None,
        ))
    return points


@router.get("/today", response_model=HealthDayDetail)
async def get_today_health(
    athlete: Annotated[Athlete, Depends(get_current_athlete)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Return today's health detail, computing readiness if not yet stored."""
    from services.readiness_service import compute_and_store_readiness

    today = date.today()
    await compute_and_store_readiness(str(athlete.id), today, db)
    return await _get_day_detail(str(athlete.id), today, db)


@router.get("/{date_str}", response_model=HealthDayDetail)
async def get_health_day(
    date_str: str,
    athlete: Annotated[Athlete, Depends(get_current_athlete)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Return detailed health data for a specific date (YYYY-MM-DD)."""
    try:
        day = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid date, use YYYY-MM-DD")
    return await _get_day_detail(str(athlete.id), day, db)


async def _get_day_detail(athlete_id: str, day: date, db: AsyncSession) -> HealthDayDetail:
    hm_result = await db.execute(
        select(HealthMetrics).where(
            HealthMetrics.athlete_id == athlete_id,
            HealthMetrics.recorded_date == day,
        )
    )
    hm = hm_result.scalar_one_or_none()

    rs_result = await db.execute(
        select(ReadinessScore).where(
            ReadinessScore.athlete_id == athlete_id,
            ReadinessScore.score_date == day,
        )
    )
    rs = rs_result.scalar_one_or_none()

    label = readiness_to_label(rs.readiness_score)[0] if rs and rs.readiness_score else None

    return HealthDayDetail(
        date=str(day),
        readiness_score=rs.readiness_score if rs else None,
        readiness_label=label,
        hrv_delta_pct=rs.hrv_delta_pct if rs else None,
        sleep_delta_pct=rs.sleep_delta_pct if rs else None,
        load_delta_pct=rs.load_delta_pct if rs else None,
        ai_summary=rs.ai_summary if rs else None,
        ai_recommendation=rs.ai_recommendation if rs else None,
        hrv_rmssd=hm.hrv_rmssd if hm else None,
        resting_hr=hm.resting_hr if hm else None,
        sleep_score=hm.sleep_score if hm else None,
        sleep_score_insight=hm.sleep_score_insight if hm else None,
        sleep_duration_minutes=hm.sleep_duration_minutes if hm else None,
        deep_sleep_minutes=hm.deep_sleep_minutes if hm else None,
        light_sleep_minutes=hm.light_sleep_minutes if hm else None,
        rem_sleep_minutes=hm.rem_sleep_minutes if hm else None,
        awake_count=hm.awake_count if hm else None,
        sleep_stress_avg=hm.sleep_stress_avg if hm else None,
        body_battery_max=hm.body_battery_max if hm else None,
        body_battery_min=hm.body_battery_min if hm else None,
        body_battery_at_wake=hm.body_battery_at_wake if hm else None,
        stress_avg=hm.stress_avg if hm else None,
        steps=hm.steps if hm else None,
        spo2_avg=hm.spo2_avg if hm else None,
    )
