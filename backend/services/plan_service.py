"""
Training plan generation and adaptive revision service.
# Uses internal schema only — not Strava API data
"""
import json
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.athlete import Athlete
from models.activity import Activity
from models.health import HealthMetrics, ReadinessScore
from models.plan import TrainingPlan, PlannedWorkout
from utils.encryption import decrypt_api_key
from utils.pace import meters_to_km, seconds_per_km_to_min_km

logger = logging.getLogger(__name__)

_DEFAULT_PLAN_WEEKS = 12


# ── Context builders ──────────────────────────────────────────────────────────

async def _build_recent_activities(athlete_id: str, db: AsyncSession) -> list[dict]:
    """Fetch last 6 weeks of runs from internal activities table."""
    # Uses internal schema only — not Strava API data
    cutoff = datetime.combine(date.today() - timedelta(weeks=6), datetime.min.time()).replace(tzinfo=timezone.utc)
    result = await db.execute(
        select(Activity).where(
            Activity.athlete_id == athlete_id,
            Activity.activity_type == "run",
            Activity.started_at >= cutoff,
        ).order_by(Activity.started_at)
    )
    activities = result.scalars().all()
    return [
        {
            "date": a.started_at.date().isoformat(),
            "type": a.activity_type,
            "workout_type": a.workout_type or "run",
            "distance_km": round(meters_to_km(a.distance_meters or 0), 1),
            "pace_str": seconds_per_km_to_min_km(a.avg_pace_seconds_per_km) if a.avg_pace_seconds_per_km else None,
            "avg_hr": a.avg_hr,
        }
        for a in activities
    ]


async def _build_health_baseline(athlete_id: str, db: AsyncSession) -> dict:
    """Compute 30-day rolling averages from health_metrics."""
    cutoff = date.today() - timedelta(days=30)
    result = await db.execute(
        select(
            func.avg(HealthMetrics.hrv_rmssd),
            func.avg(HealthMetrics.resting_hr),
            func.avg(HealthMetrics.sleep_score),
        ).where(
            HealthMetrics.athlete_id == athlete_id,
            HealthMetrics.recorded_date >= cutoff,
        )
    )
    row = result.one()

    # Last 7 days distance
    week_ago = datetime.combine(date.today() - timedelta(days=7), datetime.min.time()).replace(tzinfo=timezone.utc)
    dist_result = await db.execute(
        select(func.sum(Activity.distance_meters)).where(
            Activity.athlete_id == athlete_id,
            Activity.activity_type == "run",
            Activity.started_at >= week_ago,
        )
    )
    weekly_m = dist_result.scalar() or 0

    return {
        "hrv_avg": float(row[0]) if row[0] else None,
        "rhr_avg": float(row[1]) if row[1] else None,
        "sleep_avg": float(row[2]) if row[2] else None,
        "current_weekly_km": round(meters_to_km(weekly_m), 1),
    }


# ── Plan generation ───────────────────────────────────────────────────────────

def _parse_plan_json(raw: str) -> dict:
    """Strip markdown fences and parse plan JSON from Gemini response."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()
    data = json.loads(text)
    if "workouts" not in data or not isinstance(data["workouts"], list):
        raise ValueError("Plan JSON missing 'workouts' list")
    return data


async def generate_and_store_plan(
    athlete_id: str,
    db: AsyncSession,
    redis,
    revision_reason: str | None = None,
) -> TrainingPlan | None:
    """
    Generate a training plan via Gemini and persist it.
    Returns the new TrainingPlan, or None if Gemini not configured / quota exceeded.
    # Uses internal schema only — not Strava API data
    """
    from services.rate_limiter import check_and_increment_quota
    from services.gemini_client import call_gemini
    from prompts.training_plan import build_plan_prompt

    result = await db.execute(select(Athlete).where(Athlete.id == athlete_id))
    athlete = result.scalar_one_or_none()
    if not athlete or not athlete.gemini_api_key_encrypted:
        return None

    allowed = await check_and_increment_quota(athlete_id, redis)
    if not allowed:
        logger.warning(f"Gemini quota exceeded for plan generation — athlete {athlete_id}")
        return None

    recent_acts = await _build_recent_activities(athlete_id, db)
    health_bl = await _build_health_baseline(athlete_id, db)

    goal_race_date = None
    if athlete.goal_race_date:
        goal_race_date = athlete.goal_race_date if isinstance(athlete.goal_race_date, date) else athlete.goal_race_date.date()

    weeks_to_race = _DEFAULT_PLAN_WEEKS
    if goal_race_date:
        delta = (goal_race_date - date.today()).days
        weeks_to_race = max(4, min(delta // 7, 24))

    plan_weeks = min(weeks_to_race, _DEFAULT_PLAN_WEEKS)

    prompt = build_plan_prompt(
        athlete_name=athlete.name or "Athlete",
        goal_race_type=athlete.goal_race_type,
        goal_race_date=goal_race_date,
        goal_time_seconds=athlete.goal_finish_time_seconds,
        weeks_to_race=weeks_to_race,
        plan_weeks=plan_weeks,
        recent_activities=recent_acts,
        health_baseline=health_bl,
    )

    try:
        api_key = decrypt_api_key(athlete.gemini_api_key_encrypted)
        raw = await call_gemini(prompt=prompt, api_key=api_key, model=athlete.gemini_model, temperature=0.3, max_tokens=4096)
    except Exception as exc:
        logger.error(f"Gemini plan generation failed for athlete {athlete_id}: {exc}")
        return None

    try:
        plan_data = _parse_plan_json(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error(f"Plan JSON parse error for athlete {athlete_id}: {exc}\nRaw: {raw[:500]}")
        return None

    # Determine date range from workouts
    workout_dates = [w["date"] for w in plan_data["workouts"] if w.get("date")]
    valid_from = date.fromisoformat(min(workout_dates)) if workout_dates else date.today()
    valid_to = date.fromisoformat(max(workout_dates)) if workout_dates else (date.today() + timedelta(weeks=plan_weeks))

    # Supersede any existing active plan
    await db.execute(
        update(TrainingPlan)
        .where(TrainingPlan.athlete_id == athlete_id, TrainingPlan.status == "active")
        .values(status="superseded")
    )

    plan = TrainingPlan(
        athlete_id=athlete_id,
        valid_from=valid_from,
        valid_to=valid_to,
        goal_race_type=athlete.goal_race_type,
        goal_race_date=goal_race_date,
        goal_time_seconds=athlete.goal_finish_time_seconds,
        status="active",
        plan_summary=plan_data.get("plan_summary"),
        revision_reason=revision_reason,
        weekly_structure=plan_data.get("weekly_structure"),
    )
    db.add(plan)
    await db.flush()  # get plan.id

    for w in plan_data["workouts"]:
        try:
            scheduled = date.fromisoformat(w["date"])
        except (KeyError, ValueError):
            continue
        db.add(PlannedWorkout(
            plan_id=plan.id,
            athlete_id=athlete_id,
            scheduled_date=scheduled,
            workout_type=w.get("type", "easy"),
            title=w.get("title", "Workout"),
            description=w.get("description"),
            target_distance_meters=w.get("distance_meters"),
            target_duration_minutes=w.get("duration_minutes"),
            target_pace_min_seconds_per_km=w.get("pace_min_sec_per_km"),
            target_pace_max_seconds_per_km=w.get("pace_max_sec_per_km"),
            target_hr_zone=w.get("hr_zone"),
            target_rpe=w.get("rpe"),
            intensity_points=w.get("intensity_points"),
        ))

    await db.commit()
    await db.refresh(plan)
    logger.info(f"Training plan generated for athlete {athlete_id}: {len(plan_data['workouts'])} workouts")
    return plan


# ── Active plan queries ───────────────────────────────────────────────────────

async def get_active_plan(athlete_id: str, db: AsyncSession) -> TrainingPlan | None:
    result = await db.execute(
        select(TrainingPlan)
        .where(TrainingPlan.athlete_id == athlete_id, TrainingPlan.status == "active")
        .options(selectinload(TrainingPlan.workouts))
        .order_by(TrainingPlan.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_week_workouts(athlete_id: str, week_start: date, db: AsyncSession) -> list[dict]:
    """
    Return a 7-day view with planned workout + actual activity for each day.
    # Uses internal schema only — not Strava API data
    """
    week_end = week_start + timedelta(days=6)

    # Planned workouts
    pw_result = await db.execute(
        select(PlannedWorkout).where(
            PlannedWorkout.athlete_id == athlete_id,
            PlannedWorkout.scheduled_date >= week_start,
            PlannedWorkout.scheduled_date <= week_end,
        )
    )
    planned = {pw.scheduled_date: pw for pw in pw_result.scalars().all()}

    # Actual activities
    start_dt = datetime.combine(week_start, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(week_end + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc)
    act_result = await db.execute(
        select(Activity).where(
            Activity.athlete_id == athlete_id,
            Activity.activity_type == "run",
            Activity.started_at >= start_dt,
            Activity.started_at < end_dt,
        ).order_by(Activity.started_at)
    )
    # Group by day (take first run per day)
    actuals: dict[date, Activity] = {}
    for a in act_result.scalars().all():
        d = a.started_at.date()
        if d not in actuals:
            actuals[d] = a

    days = []
    for i in range(7):
        d = week_start + timedelta(days=i)
        pw = planned.get(d)
        act = actuals.get(d)
        days.append({
            "date": d.isoformat(),
            "planned": pw,
            "actual": act,
        })
    return days


async def get_month_workouts(athlete_id: str, year: int, month: int, db: AsyncSession) -> list[dict]:
    """Return all planned workouts for a calendar month."""
    import calendar as cal_mod
    first = date(year, month, 1)
    last_day = cal_mod.monthrange(year, month)[1]
    last = date(year, month, last_day)

    result = await db.execute(
        select(PlannedWorkout).where(
            PlannedWorkout.athlete_id == athlete_id,
            PlannedWorkout.scheduled_date >= first,
            PlannedWorkout.scheduled_date <= last,
        ).order_by(PlannedWorkout.scheduled_date)
    )
    return list(result.scalars().all())


# ── Workout completion ────────────────────────────────────────────────────────

async def mark_workout_complete(
    workout_id: str,
    athlete_id: str,
    activity_id: str | None,
    db: AsyncSession,
) -> PlannedWorkout | None:
    result = await db.execute(
        select(PlannedWorkout).where(
            PlannedWorkout.id == workout_id,
            PlannedWorkout.athlete_id == athlete_id,
        )
    )
    workout = result.scalar_one_or_none()
    if not workout:
        return None
    workout.completed = True
    if activity_id:
        workout.completed_activity_id = activity_id
    await db.commit()
    await db.refresh(workout)
    return workout


# ── Adaptive revision engine ─────────────────────────────────────────────────

async def check_revision_triggers(athlete_id: str, db: AsyncSession, redis) -> bool:
    """
    Check whether the training plan needs adaptive revision.
    Triggers: (missed workouts AND HRV suppressed) OR (critical sleep for 2+ days) OR (load spike >30%)
    Returns True if revision was triggered.
    # Uses internal schema only — not Strava API data
    """
    plan = await get_active_plan(athlete_id, db)
    if not plan:
        return False

    today = date.today()
    seven_ago = today - timedelta(days=7)

    # Count missed workouts in the past 7 days (non-rest, not completed)
    missed = sum(
        1 for w in plan.workouts
        if seven_ago <= w.scheduled_date < today
        and not w.completed
        and w.workout_type != "rest"
    )

    # HRV suppression check
    hrv_suppressed = False
    latest_readiness = await db.execute(
        select(ReadinessScore).where(
            ReadinessScore.athlete_id == athlete_id,
            ReadinessScore.score_date == today,
        )
    )
    rs = latest_readiness.scalar_one_or_none()
    if rs and rs.hrv_delta_pct is not None:
        hrv_suppressed = rs.hrv_delta_pct < -12.0

    # Critical sleep for 2+ consecutive days
    recent_readiness = await db.execute(
        select(ReadinessScore).where(
            ReadinessScore.athlete_id == athlete_id,
            ReadinessScore.score_date >= today - timedelta(days=2),
        ).order_by(ReadinessScore.score_date.desc())
    )
    rs_rows = recent_readiness.scalars().all()
    critical_sleep = sum(1 for r in rs_rows if r.sleep_delta_pct is not None and r.sleep_delta_pct < -20.0) >= 2

    # Load spike — compare last 7 days TSS to plan average
    load_spike = False
    if plan.workouts:
        recent_load = sum(
            w.intensity_points or 0 for w in plan.workouts
            if seven_ago <= w.scheduled_date < today and w.completed
        )
        avg_weekly_load = sum(w.intensity_points or 0 for w in plan.workouts) / max(len(plan.workouts) / 7, 1)
        if avg_weekly_load > 0 and recent_load > avg_weekly_load * 1.3:
            load_spike = True

    trigger = (missed >= 2 and hrv_suppressed) or critical_sleep or load_spike
    if not trigger:
        return False

    reasons = []
    if missed >= 2 and hrv_suppressed:
        reasons.append(f"{missed} missed workouts with HRV suppression ({rs.hrv_delta_pct:.0f}%)")
    if critical_sleep:
        reasons.append("critical sleep deficit for 2+ consecutive days")
    if load_spike:
        reasons.append("training load spike >30% above plan average")

    revision_reason = "Auto-revision triggered: " + "; ".join(reasons)
    logger.info(f"Plan revision triggered for athlete {athlete_id}: {revision_reason}")

    await generate_and_store_plan(athlete_id, db, redis, revision_reason=revision_reason)
    return True
