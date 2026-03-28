"""
Tests for Strava/Garmin data normalisation to internal schema.

Spec requirement:
- Strava payloads map correctly to internal activities schema
- AI layer compliance: raw_metadata is stored but normalised fields are used
- Distance, pace, and cadence conversions are correct
"""

import pytest
from datetime import datetime, timezone


MOCK_STRAVA_ACTIVITY = {
    "id": 12345678,
    "type": "Run",
    "name": "Morning Run",
    "start_date": "2025-06-15T22:30:00Z",
    "moving_time": 3600,
    "elapsed_time": 3720,
    "distance": 10000.0,                    # 10km in metres
    "total_elevation_gain": 45.0,
    "average_speed": 2.778,                 # ~10 km/h = ~6:00/km pace
    "average_heartrate": 148.0,
    "max_heartrate": 172.0,
    "average_cadence": 87.0,                # one-foot; should be doubled to 174 spm
    "workout_type": 0,                      # general run
    "perceived_exertion": 6,
    "description": "Easy morning jog",
    "gear_id": "g12345",
    "splits_metric": [
        {"distance": 1000, "moving_time": 360, "average_heartrate": 145, "elevation_difference": 5},
        {"distance": 1000, "moving_time": 365, "average_heartrate": 149, "elevation_difference": -3},
    ],
}

MOCK_GARMIN_ACTIVITY = {
    "activityId": 987654321,
    "activityType": "running",
    "startTimeInSeconds": 1718490600,       # some Unix timestamp
    "durationInSeconds": 3600,
    "distanceInMeters": 10000.0,
    "totalElevationGainInMeters": 45.0,
    "averageHeartRateInBeatsPerMinute": 148,
    "maxHeartRateInBeatsPerMinute": 172,
    "averageRunCadenceInStepsPerMinute": 174,
}


def test_strava_activity_type_normalised():
    from services.sync_service import normalise_strava_activity
    result = normalise_strava_activity(MOCK_STRAVA_ACTIVITY, "athlete-1")
    assert result["activity_type"] == "run"
    assert result["source"] == "strava"


def test_strava_external_id_is_string():
    from services.sync_service import normalise_strava_activity
    result = normalise_strava_activity(MOCK_STRAVA_ACTIVITY, "athlete-1")
    assert result["external_id"] == "12345678"


def test_strava_distance_preserved():
    from services.sync_service import normalise_strava_activity
    result = normalise_strava_activity(MOCK_STRAVA_ACTIVITY, "athlete-1")
    assert result["distance_meters"] == 10000.0


def test_strava_pace_conversion():
    """average_speed 2.778 m/s → ~360 seconds/km (6:00 min/km)"""
    from services.sync_service import normalise_strava_activity
    result = normalise_strava_activity(MOCK_STRAVA_ACTIVITY, "athlete-1")
    # 1000 / 2.778 ≈ 360 s/km
    assert abs(result["avg_pace_seconds_per_km"] - 360) < 2


def test_strava_cadence_doubled():
    """Strava provides one-foot cadence; must be doubled to get steps/min."""
    from services.sync_service import normalise_strava_activity
    result = normalise_strava_activity(MOCK_STRAVA_ACTIVITY, "athlete-1")
    assert result["avg_cadence"] == 174  # 87.0 * 2


def test_strava_splits_parsed():
    from services.sync_service import normalise_strava_activity
    result = normalise_strava_activity(MOCK_STRAVA_ACTIVITY, "athlete-1")
    assert result["splits"] is not None
    assert len(result["splits"]) == 2
    assert result["splits"][0]["km"] == 1


def test_strava_raw_metadata_stored():
    """raw_metadata must be stored; this is what compliance requires to NOT pass to AI."""
    from services.sync_service import normalise_strava_activity
    result = normalise_strava_activity(MOCK_STRAVA_ACTIVITY, "athlete-1")
    assert result["raw_metadata"] == MOCK_STRAVA_ACTIVITY


def test_garmin_activity_normalised():
    from services.sync_service import normalise_garmin_activity
    result = normalise_garmin_activity(MOCK_GARMIN_ACTIVITY, "athlete-1")
    assert result["source"] == "garmin"
    assert result["activity_type"] == "run"
    assert result["distance_meters"] == 10000.0
    assert result["avg_cadence"] == 174


def test_pace_display():
    from utils.pace import seconds_per_km_to_min_km
    assert seconds_per_km_to_min_km(360) == "6:00"
    assert seconds_per_km_to_min_km(401) == "6:41"
    assert seconds_per_km_to_min_km(0) == "--:--"


def test_duration_display():
    from utils.pace import seconds_to_duration
    assert seconds_to_duration(3723) == "1:02:03"
    assert seconds_to_duration(150) == "2:30"
