import asyncio
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


class GarminCredentialsRequest(BaseModel):
    email: str
    password: str
    mfa_code: str | None = None


class GarminTokenRequest(BaseModel):
    token_json: str   # output of garth.dumps()
    email: str | None = None


class GarminStatus(BaseModel):
    connected: bool
    email: str | None


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


# ── Garmin Connect credentials ────────────────────────────────────────────────

@router.get("/garmin", response_model=GarminStatus)
async def get_garmin_status(
    athlete: Annotated[Athlete, Depends(get_current_athlete)],
):
    return GarminStatus(
        connected=bool(athlete.garmin_tokens_encrypted),
        email=athlete.garmin_email if athlete.garmin_tokens_encrypted else None,
    )


@router.post("/garmin")
async def connect_garmin(
    request: GarminCredentialsRequest,
    athlete: Annotated[Athlete, Depends(get_current_athlete)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Log in to Garmin Connect, store encrypted tokens, trigger backfill."""
    from services.garmin_client import garmin_login
    from utils.encryption import encrypt_api_key

    try:
        tokens_json = await garmin_login(request.email, request.password, request.mfa_code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        if "RATE_LIMITED" in str(exc):
            raise HTTPException(
                status_code=429,
                detail="Garmin is rate-limiting login attempts. Wait 5–10 minutes and try again.",
            )
        raise HTTPException(status_code=502, detail=str(exc))

    athlete.garmin_email = request.email
    athlete.garmin_tokens_encrypted = encrypt_api_key(tokens_json)
    await db.commit()

    # Trigger async backfill — keep reference to prevent GC
    task = asyncio.create_task(_run_garmin_backfill(str(athlete.id)))
    task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)

    return {"status": "connected", "email": request.email}


@router.post("/garmin/token")
async def connect_garmin_token(
    request: GarminTokenRequest,
    athlete: Annotated[Athlete, Depends(get_current_athlete)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Store pre-generated garth token JSON directly (bypasses SSO rate limits)."""
    from utils.encryption import encrypt_api_key
    import functools

    # Validate by actually loading the token with garth
    def _validate(token_json: str) -> None:
        import garth
        client = garth.Client()
        client.loads(token_json.strip())
        if not client.oauth1_token and not client.oauth2_token:
            raise ValueError("Token is empty — re-run garth.dumps() after a successful login")

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, functools.partial(_validate, request.token_json))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid token — make sure you paste the full output of garth.dumps(): {exc}")

    athlete.garmin_email = request.email or athlete.garmin_email
    athlete.garmin_tokens_encrypted = encrypt_api_key(request.token_json.strip())
    await db.commit()

    task = asyncio.create_task(_run_garmin_backfill(str(athlete.id)))
    task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)

    return {"status": "connected", "email": athlete.garmin_email}


@router.delete("/garmin")
async def disconnect_garmin(
    athlete: Annotated[Athlete, Depends(get_current_athlete)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    athlete.garmin_email = None
    athlete.garmin_tokens_encrypted = None
    await db.commit()
    return {"status": "disconnected"}


async def _run_garmin_backfill(athlete_id: str):
    from database import AsyncSessionLocal
    from services.sync_service import trigger_garmin_backfill
    async with AsyncSessionLocal() as db:
        try:
            await trigger_garmin_backfill(athlete_id)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error(f"Garmin backfill error: {exc}")


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
        garmin_connected=bool(athlete.garmin_tokens_encrypted),
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
