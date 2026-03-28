from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from dependencies import get_current_athlete
from models.athlete import Athlete
from utils.encryption import encrypt_api_key, decrypt_api_key

router = APIRouter()


class GeminiKeyRequest(BaseModel):
    api_key: str
    model: str = "gemini-2.5-flash"


class GeminiKeyStatus(BaseModel):
    connected: bool
    model: str | None
    daily_usage: dict | None = None


class AthleteSettingsUpdate(BaseModel):
    name: str | None = None
    timezone: str | None = None
    goal_race_type: str | None = None
    goal_race_date: str | None = None        # ISO date string
    goal_finish_time_seconds: int | None = None


class AthleteSettingsResponse(BaseModel):
    name: str | None
    email: str
    timezone: str
    goal_race_type: str | None
    goal_race_date: str | None
    goal_finish_time_seconds: int | None
    gemini_connected: bool
    gemini_model: str
    strava_connected: bool
    garmin_connected: bool


# ── Gemini key management ──────────────────────────────────────────────────────

@router.get("/gemini", response_model=GeminiKeyStatus)
async def get_gemini_status(
    athlete: Annotated[Athlete, Depends(get_current_athlete)],
):
    return GeminiKeyStatus(
        connected=bool(athlete.gemini_api_key_encrypted),
        model=athlete.gemini_model if athlete.gemini_api_key_encrypted else None,
    )


@router.post("/gemini")
async def save_gemini_key(
    request: GeminiKeyRequest,
    athlete: Annotated[Athlete, Depends(get_current_athlete)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Encrypt and store the user's Gemini API key. Tests the key before saving."""
    # Test the key before storing
    valid, error = await _test_gemini_key(request.api_key, request.model)
    if not valid:
        raise HTTPException(status_code=400, detail=f"Invalid Gemini API key: {error}")

    athlete.gemini_api_key_encrypted = encrypt_api_key(request.api_key)
    athlete.gemini_model = request.model
    await db.commit()

    return {"status": "connected", "model": request.model}


@router.post("/gemini/test")
async def test_gemini_key(
    request: GeminiKeyRequest,
    athlete: Annotated[Athlete, Depends(get_current_athlete)],
):
    """Test a Gemini API key without saving it."""
    valid, error = await _test_gemini_key(request.api_key, request.model)
    if not valid:
        raise HTTPException(status_code=400, detail=error)
    return {"status": "valid", "model": request.model}


@router.delete("/gemini")
async def remove_gemini_key(
    athlete: Annotated[Athlete, Depends(get_current_athlete)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    athlete.gemini_api_key_encrypted = None
    await db.commit()
    return {"status": "disconnected"}


async def _test_gemini_key(api_key: str, model: str) -> tuple[bool, str | None]:
    """Send a minimal test prompt to verify the Gemini API key is valid."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "contents": [{"role": "user", "parts": [{"text": "Say OK"}]}],
        "generationConfig": {"maxOutputTokens": 5},
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.post(url, params={"key": api_key}, json=body)
            if resp.status_code == 200:
                return True, None
            elif resp.status_code == 400:
                return False, "Invalid API key format"
            elif resp.status_code == 403:
                return False, "API key is not authorised for Gemini API"
            return False, f"Unexpected response: {resp.status_code}"
    except httpx.TimeoutException:
        return False, "Connection timed out — check your internet connection"
    except Exception as e:
        return False, str(e)


# ── Athlete profile settings ──────────────────────────────────────────────────

@router.get("/profile", response_model=AthleteSettingsResponse)
async def get_profile(
    athlete: Annotated[Athlete, Depends(get_current_athlete)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from models.oauth import OAuthToken
    from sqlalchemy import select

    result = await db.execute(
        select(OAuthToken.provider).where(OAuthToken.athlete_id == athlete.id)
    )
    connected = {row[0] for row in result.fetchall()}

    return AthleteSettingsResponse(
        name=athlete.name,
        email=athlete.email,
        timezone=athlete.timezone,
        goal_race_type=athlete.goal_race_type,
        goal_race_date=str(athlete.goal_race_date) if athlete.goal_race_date else None,
        goal_finish_time_seconds=athlete.goal_finish_time_seconds,
        gemini_connected=bool(athlete.gemini_api_key_encrypted),
        gemini_model=athlete.gemini_model,
        strava_connected="strava" in connected,
        garmin_connected="garmin" in connected,
    )


@router.patch("/profile")
async def update_profile(
    body: AthleteSettingsUpdate,
    athlete: Annotated[Athlete, Depends(get_current_athlete)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from datetime import datetime

    if body.name is not None:
        athlete.name = body.name
    if body.timezone is not None:
        athlete.timezone = body.timezone
    if body.goal_race_type is not None:
        athlete.goal_race_type = body.goal_race_type
    if body.goal_race_date is not None:
        athlete.goal_race_date = datetime.strptime(body.goal_race_date, "%Y-%m-%d").date()
    if body.goal_finish_time_seconds is not None:
        athlete.goal_finish_time_seconds = body.goal_finish_time_seconds

    await db.commit()
    return {"status": "updated"}
