"""
Calendar export router — ICS download for active training plan.
"""
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from dependencies import get_current_athlete
from models.athlete import Athlete

router = APIRouter()

_WORKOUT_COLORS = {
    "easy":     "GREEN",
    "long_run": "BLUE",
    "tempo":    "YELLOW",
    "interval": "RED",
    "race":     "PURPLE",
    "rest":     "GRAY",
}


@router.get("/export.ics")
async def export_ics(
    athlete: Annotated[Athlete, Depends(get_current_athlete)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from icalendar import Calendar, Event, vText
    from services.plan_service import get_active_plan
    from utils.pace import seconds_per_km_to_min_km

    plan = await get_active_plan(athlete.id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No active training plan to export")

    cal = Calendar()
    cal.add("prodid", "-//Stryde Endurance Training//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("x-wr-calname", vText(f"Stryde Training Plan — {plan.goal_race_type or 'Endurance'}"))

    for w in sorted(plan.workouts, key=lambda x: x.scheduled_date):
        event = Event()
        event.add("summary", w.title)
        event.add("dtstart", w.scheduled_date)
        event.add("dtend", w.scheduled_date + timedelta(days=1))

        # Build description with targets
        desc_parts = []
        if w.description:
            desc_parts.append(w.description)
        if w.target_distance_meters:
            desc_parts.append(f"Distance: {w.target_distance_meters / 1000:.1f} km")
        if w.target_duration_minutes:
            desc_parts.append(f"Duration: {w.target_duration_minutes} min")
        if w.target_pace_min_seconds_per_km and w.target_pace_max_seconds_per_km:
            lo = seconds_per_km_to_min_km(w.target_pace_min_seconds_per_km)
            hi = seconds_per_km_to_min_km(w.target_pace_max_seconds_per_km)
            desc_parts.append(f"Pace: {lo}–{hi} /km")
        if w.target_hr_zone:
            desc_parts.append(f"HR Zone: {w.target_hr_zone}")
        if w.target_rpe:
            desc_parts.append(f"RPE: {w.target_rpe}/10")
        if w.completed:
            desc_parts.append("✓ Completed")

        event.add("description", "\n".join(desc_parts))
        event.add("categories", [w.workout_type.replace("_", " ").title()])
        event["color"] = _WORKOUT_COLORS.get(w.workout_type, "GRAY")
        event["uid"] = f"stryde-workout-{w.id}@stryde"

        cal.add_component(event)

    ics_bytes = cal.to_ical()
    return Response(
        content=ics_bytes,
        media_type="text/calendar",
        headers={"Content-Disposition": "attachment; filename=stryde-training-plan.ics"},
    )
