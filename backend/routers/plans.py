"""
Training plans router — CRUD, generation, week/month views.
"""
import asyncio
import logging
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from dependencies import get_current_athlete, get_redis
from models.athlete import Athlete
from models.plan import PlannedWorkout

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Response models ───────────────────────────────────────────────────────────

class PlannedWorkoutOut(BaseModel):
    id: str
    plan_id: str
    scheduled_date: date
    workout_type: str
    title: str
    description: str | None
    target_distance_meters: float | None
    target_duration_minutes: int | None
    target_pace_min_seconds_per_km: float | None
    target_pace_max_seconds_per_km: float | None
    target_hr_zone: int | None
    target_rpe: int | None
    intensity_points: float | None
    completed: bool
    completed_activity_id: str | None

    class Config:
        from_attributes = True


class TrainingPlanResponse(BaseModel):
    id: str
    created_at: datetime
    valid_from: date
    valid_to: date
    goal_race_type: str | None
    goal_race_date: date | None
    goal_time_seconds: int | None
    status: str
    plan_summary: str | None
    revision_reason: str | None
    weekly_structure: dict | None
    workouts: list[PlannedWorkoutOut]

    class Config:
        from_attributes = True


class ActivitySummaryOut(BaseModel):
    id: str
    started_at: datetime
    distance_km: float | None
    pace_str: str | None
    avg_hr: int | None
    workout_type: str | None


class WeekDayOut(BaseModel):
    date: date
    planned: PlannedWorkoutOut | None
    actual: ActivitySummaryOut | None


class WeekCalendarOut(BaseModel):
    week_start: date
    days: list[WeekDayOut]


class CompleteWorkoutRequest(BaseModel):
    activity_id: str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _run_plan_generation(athlete_id: str, revision_reason: str | None = None):
    from database import AsyncSessionLocal
    import redis.asyncio as aioredis
    from config import settings as cfg
    from services.plan_service import generate_and_store_plan

    redis = await aioredis.from_url(cfg.REDIS_URL, decode_responses=True)
    try:
        async with AsyncSessionLocal() as db:
            await generate_and_store_plan(athlete_id, db, redis, revision_reason=revision_reason)
    except Exception as exc:
        logger.error(f"Background plan generation failed for athlete {athlete_id}: {exc}")
    finally:
        await redis.aclose()


def _activity_to_summary(act) -> ActivitySummaryOut | None:
    if not act:
        return None
    from utils.pace import meters_to_km, seconds_per_km_to_min_km
    return ActivitySummaryOut(
        id=act.id,
        started_at=act.started_at,
        distance_km=round(meters_to_km(act.distance_meters or 0), 2),
        pace_str=seconds_per_km_to_min_km(act.avg_pace_seconds_per_km) if act.avg_pace_seconds_per_km else None,
        avg_hr=act.avg_hr,
        workout_type=act.workout_type,
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/active", response_model=TrainingPlanResponse)
async def get_active_plan(
    athlete: Annotated[Athlete, Depends(get_current_athlete)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from services.plan_service import get_active_plan as _get
    plan = await _get(athlete.id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No active training plan")
    return plan


@router.post("/generate")
async def generate_plan(
    athlete: Annotated[Athlete, Depends(get_current_athlete)],
):
    if not athlete.gemini_api_key_encrypted:
        raise HTTPException(status_code=400, detail="Configure your Gemini API key in Settings first")
    if not athlete.goal_race_type:
        raise HTTPException(status_code=400, detail="Set a goal race type in Settings before generating a plan")
    if not athlete.goal_race_date:
        raise HTTPException(status_code=400, detail="Set a goal race date in Settings before generating a plan")
    task = asyncio.create_task(_run_plan_generation(athlete.id))
    task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
    return {"status": "generating", "message": "Plan generation started — check back in ~30 seconds"}


@router.get("/workouts/week", response_model=WeekCalendarOut)
async def get_week_calendar(
    start: str,
    athlete: Annotated[Athlete, Depends(get_current_athlete)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        week_start = date.fromisoformat(start)
    except ValueError:
        raise HTTPException(status_code=400, detail="start must be YYYY-MM-DD")

    from services.plan_service import get_week_workouts
    days_raw = await get_week_workouts(athlete.id, week_start, db)

    days_out = [
        WeekDayOut(
            date=date.fromisoformat(d["date"]),
            planned=PlannedWorkoutOut.model_validate(d["planned"]) if d["planned"] else None,
            actual=_activity_to_summary(d["actual"]),
        )
        for d in days_raw
    ]
    return WeekCalendarOut(week_start=week_start, days=days_out)


@router.get("/workouts/month", response_model=list[PlannedWorkoutOut])
async def get_month_calendar(
    year: int,
    month: int,
    athlete: Annotated[Athlete, Depends(get_current_athlete)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from services.plan_service import get_month_workouts
    workouts = await get_month_workouts(athlete.id, year, month, db)
    return workouts


@router.post("/workouts/{workout_id}/complete", response_model=PlannedWorkoutOut)
async def complete_workout(
    workout_id: str,
    body: CompleteWorkoutRequest,
    athlete: Annotated[Athlete, Depends(get_current_athlete)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from services.plan_service import mark_workout_complete
    workout = await mark_workout_complete(workout_id, athlete.id, body.activity_id, db)
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    return workout


@router.get("/{plan_id}", response_model=TrainingPlanResponse)
async def get_plan_by_id(
    plan_id: str,
    athlete: Annotated[Athlete, Depends(get_current_athlete)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from models.plan import TrainingPlan

    result = await db.execute(
        select(TrainingPlan)
        .where(TrainingPlan.id == plan_id, TrainingPlan.athlete_id == athlete.id)
        .options(selectinload(TrainingPlan.workouts))
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan
