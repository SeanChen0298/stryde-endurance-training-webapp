from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from dependencies import get_current_athlete
from models.activity import Activity
from models.athlete import Athlete
from utils.pace import seconds_per_km_to_min_km, seconds_to_duration, meters_to_km

router = APIRouter()


class ActivitySummary(BaseModel):
    id: str
    activity_type: str
    workout_type: str | None
    started_at: str
    distance_km: float | None
    duration_str: str | None
    pace_str: str | None
    avg_hr: int | None
    max_hr: int | None
    elevation_gain_m: float | None
    source: str
    gear_id: str | None


class ActivityDetail(ActivitySummary):
    avg_cadence: int | None
    avg_power: int | None
    hr_zone_distribution: dict | None
    splits: list | None
    notes: str | None
    perceived_effort: int | None


class ActivitiesListResponse(BaseModel):
    total: int
    page: int
    per_page: int
    items: list[ActivitySummary]


class MonthlySummary(BaseModel):
    total_km: float
    total_runs: int
    total_duration_seconds: int
    avg_hr: float | None


def _to_summary(a: Activity) -> ActivitySummary:
    return ActivitySummary(
        id=str(a.id),
        activity_type=a.activity_type,
        workout_type=a.workout_type,
        started_at=a.started_at.isoformat(),
        distance_km=meters_to_km(a.distance_meters) if a.distance_meters else None,
        duration_str=seconds_to_duration(a.duration_seconds) if a.duration_seconds else None,
        pace_str=seconds_per_km_to_min_km(a.avg_pace_seconds_per_km) if a.avg_pace_seconds_per_km else None,
        avg_hr=a.avg_hr,
        max_hr=a.max_hr,
        elevation_gain_m=a.elevation_gain_meters,
        source=a.source,
        gear_id=a.gear_id,
    )


@router.get("", response_model=ActivitiesListResponse)
async def list_activities(
    athlete: Annotated[Athlete, Depends(get_current_athlete)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    activity_type: str | None = Query(None),
    workout_type: str | None = Query(None),
):
    query = select(Activity).where(Activity.athlete_id == athlete.id)

    if activity_type:
        query = query.where(Activity.activity_type == activity_type)
    if workout_type:
        query = query.where(Activity.workout_type == workout_type)

    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar_one()

    query = query.order_by(desc(Activity.started_at)).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    activities = result.scalars().all()

    return ActivitiesListResponse(
        total=total,
        page=page,
        per_page=per_page,
        items=[_to_summary(a) for a in activities],
    )


@router.get("/monthly-summary", response_model=MonthlySummary)
async def get_monthly_summary(
    athlete: Annotated[Athlete, Depends(get_current_athlete)],
    db: Annotated[AsyncSession, Depends(get_db)],
    year: int = Query(None),
    month: int = Query(None),
):
    from datetime import date, timedelta

    now = datetime.utcnow()
    y = year or now.year
    m = month or now.month

    start = datetime(y, m, 1)
    if m == 12:
        end = datetime(y + 1, 1, 1)
    else:
        end = datetime(y, m + 1, 1)

    result = await db.execute(
        select(
            func.sum(Activity.distance_meters),
            func.count(Activity.id),
            func.sum(Activity.duration_seconds),
            func.avg(Activity.avg_hr),
        ).where(
            Activity.athlete_id == athlete.id,
            Activity.activity_type == "run",
            Activity.started_at >= start,
            Activity.started_at < end,
        )
    )
    row = result.one()
    return MonthlySummary(
        total_km=meters_to_km(row[0] or 0),
        total_runs=row[1] or 0,
        total_duration_seconds=row[2] or 0,
        avg_hr=round(row[3], 1) if row[3] else None,
    )


@router.get("/{activity_id}", response_model=ActivityDetail)
async def get_activity(
    activity_id: str,
    athlete: Annotated[Athlete, Depends(get_current_athlete)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Activity).where(
            Activity.id == activity_id,
            Activity.athlete_id == athlete.id,
        )
    )
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    summary = _to_summary(activity)
    return ActivityDetail(
        **summary.model_dump(),
        avg_cadence=activity.avg_cadence,
        avg_power=activity.avg_power,
        hr_zone_distribution=activity.hr_zone_distribution,
        splits=activity.splits,
        notes=activity.notes,
        perceived_effort=activity.perceived_effort,
    )
