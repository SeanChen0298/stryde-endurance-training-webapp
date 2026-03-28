"""Pace and speed conversion helpers."""


def seconds_per_km_to_min_km(seconds: float) -> str:
    """Convert seconds/km to MM:SS/km display string. e.g. 360 → '6:00'"""
    if not seconds or seconds <= 0:
        return "--:--"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"


def min_km_to_seconds(pace_str: str) -> float:
    """Parse 'M:SS' pace string to seconds/km. e.g. '6:00' → 360.0"""
    parts = pace_str.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid pace format: {pace_str}")
    return int(parts[0]) * 60 + int(parts[1])


def seconds_to_duration(total_seconds: int) -> str:
    """Format seconds as H:MM:SS or M:SS. e.g. 3723 → '1:02:03'"""
    if total_seconds < 0:
        return "--"
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def meters_to_km(meters: float, decimals: int = 1) -> float:
    """Convert metres to kilometres."""
    return round(meters / 1000, decimals)


def km_to_meters(km: float) -> float:
    return km * 1000


def pace_zone_label(pace_s: float, threshold_s: float) -> str:
    """
    Classify pace relative to threshold pace.
    Returns: 'easy' | 'moderate' | 'threshold' | 'interval' | 'sprint'
    """
    ratio = pace_s / threshold_s
    if ratio >= 1.25:
        return "easy"
    elif ratio >= 1.10:
        return "moderate"
    elif ratio >= 0.95:
        return "threshold"
    elif ratio >= 0.85:
        return "interval"
    return "sprint"


def estimate_hr_zones(max_hr: int) -> dict:
    """
    Estimate HR zone boundaries using % of max HR (Garmin method).
    Returns dict of zone number → (min_bpm, max_bpm).
    """
    return {
        1: (0, int(max_hr * 0.60)),
        2: (int(max_hr * 0.60), int(max_hr * 0.70)),
        3: (int(max_hr * 0.70), int(max_hr * 0.80)),
        4: (int(max_hr * 0.80), int(max_hr * 0.90)),
        5: (int(max_hr * 0.90), max_hr),
    }


def compute_hr_zone_distribution(avg_hr: int | None, max_hr: int | None) -> dict | None:
    """
    Rough HR zone distribution estimate from avg_hr + max_hr.
    For real distribution, lap-level HR data is needed.
    """
    if not avg_hr or not max_hr:
        return None
    zones = estimate_hr_zones(max_hr)
    # Determine which zone avg_hr falls in
    main_zone = 2
    for z, (lo, hi) in zones.items():
        if lo <= avg_hr < hi:
            main_zone = z
            break
    # Simple gaussian-ish distribution centred on main zone
    dist_map = {
        1: {1: 0.70, 2: 0.20, 3: 0.07, 4: 0.02, 5: 0.01},
        2: {1: 0.20, 2: 0.60, 3: 0.15, 4: 0.04, 5: 0.01},
        3: {1: 0.05, 2: 0.25, 3: 0.50, 4: 0.15, 5: 0.05},
        4: {1: 0.02, 2: 0.08, 3: 0.25, 4: 0.50, 5: 0.15},
        5: {1: 0.01, 2: 0.04, 3: 0.10, 4: 0.35, 5: 0.50},
    }
    return {f"z{k}": v for k, v in dist_map[main_zone].items()}
