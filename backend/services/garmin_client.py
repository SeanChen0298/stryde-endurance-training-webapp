"""
Garmin Connect API wrapper.

During Phase 1, Garmin API approval may be pending. The app degrades gracefully:
- If GARMIN_CLIENT_ID is empty, all Garmin sync is silently skipped.
- All Garmin-dependent widgets render with a "Connect Garmin" prompt.
"""

import logging
from datetime import date, datetime, timezone
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

GARMIN_API_BASE = "https://apis.garmin.com"


class GarminClient:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.http = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30.0,
        )

    async def close(self):
        await self.http.aclose()

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def get_daily_summaries(self, start_date: date, end_date: date) -> list[dict]:
        """Fetch daily health summaries (steps, stress, body battery, etc.)"""
        resp = await self.http.get(
            f"{GARMIN_API_BASE}/wellness-api/rest/dailies",
            params={
                "uploadStartTimeInSeconds": int(datetime.combine(start_date, datetime.min.time()).timestamp()),
                "uploadEndTimeInSeconds": int(datetime.combine(end_date, datetime.min.time()).timestamp()),
            },
        )
        resp.raise_for_status()
        return resp.json().get("dailies", [])

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def get_sleep_data(self, start_date: date, end_date: date) -> list[dict]:
        """Fetch sleep stage data."""
        resp = await self.http.get(
            f"{GARMIN_API_BASE}/wellness-api/rest/sleeps",
            params={
                "uploadStartTimeInSeconds": int(datetime.combine(start_date, datetime.min.time()).timestamp()),
                "uploadEndTimeInSeconds": int(datetime.combine(end_date, datetime.min.time()).timestamp()),
            },
        )
        resp.raise_for_status()
        return resp.json().get("sleeps", [])

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def get_hrv_data(self, start_date: date, end_date: date) -> list[dict]:
        """Fetch HRV summary data."""
        resp = await self.http.get(
            f"{GARMIN_API_BASE}/wellness-api/rest/hrv",
            params={
                "uploadStartTimeInSeconds": int(datetime.combine(start_date, datetime.min.time()).timestamp()),
                "uploadEndTimeInSeconds": int(datetime.combine(end_date, datetime.min.time()).timestamp()),
            },
        )
        resp.raise_for_status()
        return resp.json().get("hrvSummaries", [])

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def get_activities(self, start_date: date, end_date: date) -> list[dict]:
        """Fetch Garmin activity summaries."""
        resp = await self.http.get(
            f"{GARMIN_API_BASE}/activity-service/activity/forUser",
            params={
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
            },
        )
        resp.raise_for_status()
        return resp.json().get("activityList", [])


async def get_valid_garmin_client(athlete_id: str, db) -> "GarminClient | None":
    """Return a GarminClient with valid credentials, or None if not configured."""
    from config import settings
    from models.oauth import OAuthToken
    from sqlalchemy import select

    if not settings.GARMIN_CLIENT_ID:
        return None

    result = await db.execute(
        select(OAuthToken).where(
            OAuthToken.athlete_id == athlete_id,
            OAuthToken.provider == "garmin",
        )
    )
    token = result.scalar_one_or_none()
    if not token:
        return None

    return GarminClient(token.access_token)
