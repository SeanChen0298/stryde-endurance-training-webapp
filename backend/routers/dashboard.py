"""
Dashboard router — aggregated stats for the frontend overview page.
Serves Phase 1 data: weekly mileage, recent activities, HRV/sleep trends.
"""

from datetime import datetime, timedelta, date
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from dependencies import get_current_athlete
from models.activity import Activity
from models.athlete import Athlete
from models.health import HealthMetrics, ReadinessScore
from utils.hrv import readiness_to_label
from utils.pace import seconds_per_km_to_min_km, seconds_to_duration, meters_to_km

router = APIRouter()


class WeeklyMileage(BaseModel):
    current_km: float
    target_km: float | None
    run_count: int
    daily_runs: list[float]          # 7 values, Mon–Sun (0 = no run)


class RecentActivity(BaseModel):
    id: str
    activity_type: str
    workout_type: str | None
    started_at: str
    distance_km: float | None
    pace_str: str | None
    duration_str: str | None
    avg_hr: int | None
    source: str


class HRVPoint(BaseModel):
    date: str
    value: float | None


class SleepPoint(BaseModel):
    date: str
    score: int | None
    duration_minutes: int | None


class DashboardData(BaseModel):
    # Phase 1
    weekly_mileage: WeeklyMileage
    recent_activities: list[RecentActivity]
    hrv_trend: list[HRVPoint]            # last 14 days
    sleep_trend: list[SleepPoint]        # last 14 days
    gemini_connected: bool
    garmin_connected: bool
    strava_connected: bool

    # Phase 2+ (None in Phase 1)
    readiness_score: float | None = None
    readiness_label: str | None = None
    ai_brief: str | None = None


@router.get("", response_model=DashboardData)
async def get_dashboard(
    athlete: Annotated[Athlete, Depends(get_current_athlete)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    now = datetime.utcnow()
    week_start = now - timedelta(days=now.weekday())  # Monday of current week
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

    # ── Weekly mileage ────────────────────────────────────────────────────────
    result = await db.execute(
        select(Activity).where(
            Activity.athlete_id == athlete.id,
            Activity.activity_type == "run",
            Activity.started_at >= week_start,
        ).order_by(Activity.started_at)
    )
    week_activities = result.scalars().all()

    daily_runs = [0.0] * 7
    current_km = 0.0
    for a in week_activities:
        dow = a.started_at.weekday()  # 0=Mon, 6=Sun
        km = meters_to_km(a.distance_meters or 0)
        daily_runs[dow] += km
        current_km += km

    weekly_mileage = WeeklyMileage(
        current_km=round(current_km, 1),
        target_km=None,      # Phase 3: comes from training plan
        run_count=len(week_activities),
        daily_runs=[round(d, 1) for d in daily_runs],
    )

    # ── Recent activities (last 5) ────────────────────────────────────────────
    result = await db.execute(
        select(Activity)
        .where(Activity.athlete_id == athlete.id)
        .order_by(desc(Activity.started_at))
        .limit(5)
    )
    recent_raw = result.scalars().all()
    recent_activities = [
        RecentActivity(
            id=str(a.id),
            activity_type=a.activity_type,
            workout_type=a.workout_type,
            started_at=a.started_at.isoformat(),
            distance_km=meters_to_km(a.distance_meters) if a.distance_meters else None,
            pace_str=seconds_per_km_to_min_km(a.avg_pace_seconds_per_km) if a.avg_pace_seconds_per_km else None,
            duration_str=seconds_to_duration(a.duration_seconds) if a.duration_seconds else None,
            avg_hr=a.avg_hr,
            source=a.source,
        )
        for a in recent_raw
    ]

    # ── HRV + Sleep trends (last 14 days) ────────────────────────────────────
    fourteen_days_ago = date.today() - timedelta(days=14)
    result = await db.execute(
        select(HealthMetrics)
        .where(
            HealthMetrics.athlete_id == athlete.id,
            HealthMetrics.recorded_date >= fourteen_days_ago,
        )
        .order_by(HealthMetrics.recorded_date)
    )
    health_rows = result.scalars().all()
    health_by_date = {str(h.recorded_date): h for h in health_rows}

    hrv_trend = []
    sleep_trend = []
    for i in range(14):
        d = str(date.today() - timedelta(days=13 - i))
        h = health_by_date.get(d)
        hrv_trend.append(HRVPoint(date=d, value=h.hrv_rmssd if h else None))
        sleep_trend.append(SleepPoint(
            date=d,
            score=h.sleep_score if h else None,
            duration_minutes=h.sleep_duration_minutes if h else None,
        ))

    # ── Connection status ─────────────────────────────────────────────────────
    from models.oauth import OAuthToken
    result = await db.execute(
        select(OAuthToken.provider).where(OAuthToken.athlete_id == athlete.id)
    )
    connected = {row[0] for row in result.fetchall()}

    # ── Phase 2: today's readiness score + AI brief ───────────────────────────
    readiness_score = None
    readiness_label = None
    ai_brief = None

    result = await db.execute(
        select(ReadinessScore).where(
            ReadinessScore.athlete_id == athlete.id,
            ReadinessScore.score_date == date.today(),
        )
    )
    rs = result.scalar_one_or_none()
    if rs:
        readiness_score = rs.readiness_score
        if rs.readiness_score:
            readiness_label = readiness_to_label(rs.readiness_score)[0]
        ai_brief = rs.ai_summary

    return DashboardData(
        weekly_mileage=weekly_mileage,
        recent_activities=recent_activities,
        hrv_trend=hrv_trend,
        sleep_trend=sleep_trend,
        gemini_connected=bool(athlete.gemini_api_key_encrypted),
        garmin_connected=bool(athlete.garmin_tokens_encrypted),
        strava_connected="strava" in connected,
        readiness_score=readiness_score,
        readiness_label=readiness_label,
        ai_brief=ai_brief,
    )
