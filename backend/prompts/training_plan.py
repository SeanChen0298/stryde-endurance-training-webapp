"""
Training plan prompt builder.
# Uses internal schema only — not Strava API data
"""
from datetime import date


def build_plan_prompt(
    athlete_name: str,
    goal_race_type: str | None,
    goal_race_date: date | None,
    goal_time_seconds: int | None,
    weeks_to_race: int,
    plan_weeks: int,
    recent_activities: list[dict],  # internal schema: date, type, distance_km, pace_str, avg_hr
    health_baseline: dict,          # hrv_avg, rhr_avg, sleep_avg, current_weekly_km
) -> str:
    # Uses internal schema only — not Strava API data

    goal_race = goal_race_type.replace("_", " ").title() if goal_race_type else "general endurance"
    goal_date_str = goal_race_date.isoformat() if goal_race_date else "not set"

    if goal_time_seconds:
        h = goal_time_seconds // 3600
        m = (goal_time_seconds % 3600) // 60
        goal_time_str = f"{h}:{m:02d}:00" if h else f"{m}:{goal_time_seconds % 60:02d}"
    else:
        goal_time_str = "no specific goal time"

    # Build recent activity table (last 6 weeks, max 42 rows)
    act_lines = []
    for a in recent_activities[-42:]:
        pace = a.get("pace_str") or "--"
        hr = f"{a['avg_hr']} bpm" if a.get("avg_hr") else "--"
        act_lines.append(
            f"  {a['date']}  {a.get('workout_type', a.get('type', 'run')):10s}  "
            f"{a['distance_km']:5.1f} km  {pace}/km  {hr}"
        )
    activity_table = "\n".join(act_lines) if act_lines else "  No recent activities found."

    hrv = f"{health_baseline.get('hrv_avg', 0):.1f} ms" if health_baseline.get("hrv_avg") else "unknown"
    rhr = f"{health_baseline.get('rhr_avg', 0):.0f} bpm" if health_baseline.get("rhr_avg") else "unknown"
    sleep = f"{health_baseline.get('sleep_avg', 0):.0f}/100" if health_baseline.get("sleep_avg") else "unknown"
    weekly_km = f"{health_baseline.get('current_weekly_km', 0):.1f} km"

    return f"""You are an expert endurance running coach. Generate a personalised {plan_weeks}-week training plan.

ATHLETE: {athlete_name}
GOAL: {goal_race} on {goal_date_str} ({weeks_to_race} weeks away)
TARGET TIME: {goal_time_str}
CURRENT WEEKLY VOLUME: {weekly_km}
HRV BASELINE: {hrv}
RESTING HR: {rhr}
SLEEP SCORE: {sleep}

RECENT TRAINING (last 6 weeks — internal schema only):
{activity_table}

INSTRUCTIONS:
- Use polarised periodisation: ~80% easy, ~10% threshold, ~10% high intensity
- Respect Malaysia's tropical climate: reduce intensity for heat (above 30°C is normal)
- Build volume gradually: max 10% increase per week
- Include a full rest day each week
- Peak week 2–3 weeks before the race, then taper
- Each workout must have realistic distance AND duration targets
- Pace zones based on current fitness (infer from recent paces above)

Return ONLY a valid JSON object with no markdown, no explanation, exactly this structure:
{{
  "plan_summary": "2–3 sentence plain English description of the periodisation approach",
  "weekly_structure": {{
    "base_weeks": [1, 2, 3, 4],
    "build_weeks": [5, 6, 7, 8],
    "peak_weeks": [9, 10],
    "taper_weeks": [11, 12]
  }},
  "workouts": [
    {{
      "date": "YYYY-MM-DD",
      "type": "easy|long_run|tempo|interval|rest|race",
      "title": "short title",
      "description": "1–2 sentences of coaching cues",
      "distance_meters": 8000,
      "duration_minutes": 50,
      "pace_min_sec_per_km": 330,
      "pace_max_sec_per_km": 360,
      "hr_zone": 2,
      "rpe": 4,
      "intensity_points": 42.0
    }}
  ]
}}

Generate workouts starting from tomorrow ({date.today().isoformat()}) for {plan_weeks} weeks.
For rest days set distance_meters, duration_minutes, pace_min_sec_per_km, pace_max_sec_per_km to null and hr_zone to null.
"""
