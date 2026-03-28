"""HRV baseline and readiness calculation helpers."""

from datetime import date
from statistics import mean, stdev


def compute_hrv_baseline(readings: list[float], window_days: int = 30) -> dict:
    """
    Compute HRV baseline stats over the rolling window.

    Args:
        readings: list of HRV RMSSD values (most recent last), max window_days length
        window_days: number of days for baseline window

    Returns:
        dict with mean, stdev, cv (coefficient of variation)
    """
    recent = readings[-window_days:] if len(readings) >= window_days else readings
    if not recent:
        return {"mean": None, "stdev": None, "cv": None}

    m = mean(recent)
    s = stdev(recent) if len(recent) > 1 else 0.0
    cv = (s / m) if m > 0 else 0.0

    return {"mean": round(m, 1), "stdev": round(s, 1), "cv": round(cv, 3)}


def hrv_delta_pct(current: float, baseline_mean: float) -> float:
    """
    Calculate percentage deviation of today's HRV from the rolling mean.
    Positive = above baseline (good), negative = below (stressed).
    """
    if not baseline_mean or baseline_mean == 0:
        return 0.0
    return round((current - baseline_mean) / baseline_mean * 100, 1)


def compute_readiness_score(
    hrv_delta: float | None,
    sleep_delta: float | None,
    resting_hr_delta: float | None,
    load_delta: float | None,
) -> float:
    """
    Compute a 0–100 readiness score from component deltas.

    Weights:
    - HRV deviation: 40%
    - Sleep score delta: 30%
    - Resting HR delta (inverted): 15%
    - Training load delta (inverted): 15%
    """
    score = 75.0  # neutral baseline

    if hrv_delta is not None:
        # +1% HRV → +0.4 score; -1% → -0.4
        score += hrv_delta * 0.4

    if sleep_delta is not None:
        # sleep_delta: % deviation from 7-day avg sleep score
        score += sleep_delta * 0.3

    if resting_hr_delta is not None:
        # resting_hr_delta: % change from baseline (lower HR = better)
        # negative delta (lower HR) → positive readiness contribution
        score += (-resting_hr_delta) * 0.15

    if load_delta is not None:
        # load_delta: % deviation of today's ATL from 7-day avg
        # high load → lower readiness
        score += (-max(0, load_delta)) * 0.15

    return round(max(0.0, min(100.0, score)), 1)


def readiness_to_label(score: float) -> tuple[str, str]:
    """
    Convert readiness score to (label, css_class).
    Returns: ('Optimal', 'status-green') | ('Ready', 'status-green') | ('Moderate', 'status-amber') | ('Low', 'status-red')
    """
    if score >= 85:
        return "Optimal", "status-green"
    elif score >= 70:
        return "Ready to train", "status-green"
    elif score >= 50:
        return "Moderate — take it easy", "status-amber"
    return "Low — rest day recommended", "status-red"
