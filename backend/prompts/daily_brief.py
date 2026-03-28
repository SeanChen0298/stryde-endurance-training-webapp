"""
Prompt builder for the daily AI readiness brief.
# Uses internal schema only — not Strava API data
"""
from datetime import date


def build_daily_brief_prompt(
    athlete_name: str | None,
    for_date: date,
    readiness_score: float,
    hrv_delta: float | None,
    sleep_delta: float | None,
    load_delta: float | None,
    recent_activities: list[dict],  # internal schema fields only
    goal_race_type: str | None,
    goal_race_date: date | None,
    goal_finish_time_seconds: int | None,
) -> str:
    """
    Build the Gemini prompt for the daily brief.
    # Uses internal schema only — not Strava API data
    """
    name = athlete_name or "the athlete"

    days_to_race = None
    if goal_race_date:
        delta = (goal_race_date - for_date).days
        if delta > 0:
            days_to_race = delta

    act_lines = []
    for a in recent_activities[-7:]:
        dist = a.get("distance_km", 0) or 0
        pace = a.get("pace_str") or "—"
        hr = a.get("avg_hr") or "—"
        wtype = (a.get("workout_type") or "").replace("_", " ")
        started = (a.get("started_at") or "")[:10]
        act_lines.append(f"  - {started}: {dist:.1f} km {wtype} | pace {pace}/km | HR {hr}")

    activities_section = "\n".join(act_lines) if act_lines else "  - No recent run data"

    goal_section = ""
    if goal_race_type and days_to_race:
        finish = ""
        if goal_finish_time_seconds:
            h, rem = divmod(goal_finish_time_seconds, 3600)
            m = rem // 60
            finish = f", target {h}h{m:02d}m"
        goal_section = f"\nGoal: {goal_race_type.replace('_', ' ')} in {days_to_race} days{finish}."

    hrv_str = f"{hrv_delta:+.1f}% vs 30-day baseline" if hrv_delta is not None else "no HRV data"
    sleep_str = f"{sleep_delta:+.1f}% vs 7-day avg" if sleep_delta is not None else "no sleep data"
    load_str = f"{load_delta:+.1f}% yesterday vs 7-day avg" if load_delta is not None else "no load data"

    return f"""You are a concise AI running coach delivering a morning brief for {name}.
Date: {for_date.strftime('%A %d %B %Y')}
Readiness score: {readiness_score:.0f}/100
HRV: {hrv_str}
Sleep quality: {sleep_str}
Training load: {load_str}
Recent activities:
{activities_section}{goal_section}

Reply with exactly 3 bullet points starting with "•". Be specific, data-driven, and direct.
• Bullet 1: Readiness status and what it means for today's training.
• Bullet 2: The most important trend to watch (HRV, sleep, or load).
• Bullet 3: Specific recommended action or workout for today.
Max 25 words per bullet. No preamble, no sign-off, no markdown beyond the bullets."""
