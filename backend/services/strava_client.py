"""
Strava API wrapper.

Compliance note: Raw Strava API payloads are written to activities.raw_metadata
and immediately discarded. All downstream processing (AI, analysis) reads only
from the normalised activities table — never from raw_metadata.
"""

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

STRAVA_API_BASE = "https://www.strava.com/api/v3"
STRAVA_AUTH_BASE = "https://www.strava.com/oauth"


class StravaClient:
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
    async def get_athlete(self) -> dict:
        resp = await self.http.get(f"{STRAVA_API_BASE}/athlete")
        resp.raise_for_status()
        return resp.json()

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def get_activity(self, activity_id: int) -> dict:
        resp = await self.http.get(f"{STRAVA_API_BASE}/activities/{activity_id}", params={"include_all_efforts": True})
        resp.raise_for_status()
        return resp.json()

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def list_activities(self, after: int | None = None, per_page: int = 50, page: int = 1) -> list[dict]:
        params: dict[str, Any] = {"per_page": per_page, "page": page}
        if after:
            params["after"] = after
        resp = await self.http.get(f"{STRAVA_API_BASE}/athlete/activities", params=params)
        resp.raise_for_status()
        return resp.json()

    async def list_gear(self) -> list[dict]:
        athlete = await self.get_athlete()
        return athlete.get("shoes", []) + athlete.get("bikes", [])

    async def get_gear(self, gear_id: str) -> dict:
        resp = await self.http.get(f"{STRAVA_API_BASE}/gear/{gear_id}")
        resp.raise_for_status()
        return resp.json()


async def exchange_code_for_token(client_id: str, client_secret: str, code: str) -> dict:
    """Exchange OAuth authorization code for access + refresh tokens."""
    async with httpx.AsyncClient() as http:
        resp = await http.post(
            f"{STRAVA_AUTH_BASE}/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> dict:
    """Refresh an expired Strava access token."""
    async with httpx.AsyncClient() as http:
        resp = await http.post(
            f"{STRAVA_AUTH_BASE}/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def get_valid_strava_client(athlete_id: str, db) -> StravaClient | None:
    """Return a StravaClient with a fresh token, refreshing if needed."""
    from models.oauth import OAuthToken
    from sqlalchemy import select

    result = await db.execute(
        select(OAuthToken).where(
            OAuthToken.athlete_id == athlete_id,
            OAuthToken.provider == "strava",
        )
    )
    token = result.scalar_one_or_none()
    if not token:
        return None

    now = datetime.now(timezone.utc)
    if token.expires_at and token.expires_at < now:
        from config import settings
        refreshed = await refresh_access_token(
            settings.STRAVA_CLIENT_ID,
            settings.STRAVA_CLIENT_SECRET,
            token.refresh_token,
        )
        token.access_token = refreshed["access_token"]
        token.refresh_token = refreshed.get("refresh_token", token.refresh_token)
        token.expires_at = datetime.fromtimestamp(refreshed["expires_at"], tz=timezone.utc)
        await db.commit()

    return StravaClient(token.access_token)
