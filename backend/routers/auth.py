from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from dependencies import get_current_athlete
from models.athlete import Athlete
from utils.jwt import create_access_token, verify_password

router = APIRouter()

STRAVA_AUTH_URL = (
    "https://www.strava.com/oauth/authorize"
    "?client_id={client_id}"
    "&redirect_uri={redirect_uri}"
    "&response_type=code"
    "&scope=read,activity:read_all,profile:read_all"
)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    athlete_name: str | None = None
    gemini_connected: bool = False


class AthleteProfile(BaseModel):
    id: str
    email: str
    name: str | None
    timezone: str
    goal_race_type: str | None
    goal_race_date: str | None
    goal_finish_time_seconds: int | None
    gemini_connected: bool
    gemini_model: str
    strava_connected: bool
    garmin_connected: bool


# ── Login / Logout ────────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse)
async def login(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Athlete).where(Athlete.email == form_data.username))
    athlete = result.scalar_one_or_none()

    if not athlete or not verify_password(form_data.password, athlete.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(subject=str(athlete.id))

    response.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.JWT_EXPIRE_HOURS * 3600,
    )

    return LoginResponse(
        access_token=token,
        athlete_name=athlete.name,
        gemini_connected=bool(athlete.gemini_api_key_encrypted),
    )


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logged out"}


@router.get("/me", response_model=AthleteProfile)
async def get_me(
    athlete: Annotated[Athlete, Depends(get_current_athlete)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from models.oauth import OAuthToken

    result = await db.execute(
        select(OAuthToken.provider).where(OAuthToken.athlete_id == athlete.id)
    )
    connected = {row[0] for row in result.fetchall()}

    return AthleteProfile(
        id=str(athlete.id),
        email=athlete.email,
        name=athlete.name,
        timezone=athlete.timezone,
        goal_race_type=athlete.goal_race_type,
        goal_race_date=str(athlete.goal_race_date) if athlete.goal_race_date else None,
        goal_finish_time_seconds=athlete.goal_finish_time_seconds,
        gemini_connected=bool(athlete.gemini_api_key_encrypted),
        gemini_model=athlete.gemini_model,
        strava_connected="strava" in connected,
        garmin_connected="garmin" in connected,
    )


# ── Strava OAuth ──────────────────────────────────────────────────────────────

@router.get("/strava/url")
async def strava_oauth_url(athlete: Annotated[Athlete, Depends(get_current_athlete)]):
    """Return the Strava OAuth URL for the frontend to redirect to."""
    redirect_uri = settings.STRAVA_WEBHOOK_CALLBACK_URL
    url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={settings.STRAVA_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=read,activity:read_all,profile:read_all"
    )
    return {"url": url}


@router.get("/strava")
async def strava_oauth_redirect(athlete: Annotated[Athlete, Depends(get_current_athlete)]):
    """Redirect user to Strava OAuth consent page."""
    redirect_uri = settings.STRAVA_WEBHOOK_CALLBACK_URL
    url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={settings.STRAVA_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=read,activity:read_all,profile:read_all"
    )
    return RedirectResponse(url)


@router.get("/strava/callback")
async def strava_callback(
    code: str,
    athlete: Annotated[Athlete, Depends(get_current_athlete)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Handle Strava OAuth callback, store tokens, trigger backfill."""
    from datetime import datetime, timezone as tz
    from models.oauth import OAuthToken
    from services.strava_client import exchange_code_for_token
    from services.sync_service import trigger_strava_backfill

    token_data = await exchange_code_for_token(
        settings.STRAVA_CLIENT_ID,
        settings.STRAVA_CLIENT_SECRET,
        code,
    )

    # Upsert token
    result = await db.execute(
        select(OAuthToken).where(
            OAuthToken.athlete_id == athlete.id,
            OAuthToken.provider == "strava",
        )
    )
    token = result.scalar_one_or_none()

    if not token:
        token = OAuthToken(athlete_id=athlete.id, provider="strava")
        db.add(token)

    token.access_token = token_data["access_token"]
    token.refresh_token = token_data.get("refresh_token")
    token.expires_at = datetime.fromtimestamp(token_data["expires_at"], tz=tz.utc)
    token.scope = token_data.get("scope", "")

    # Store Strava athlete ID
    strava_athlete = token_data.get("athlete", {})
    if strava_athlete.get("id"):
        athlete.strava_athlete_id = strava_athlete["id"]

    await db.commit()

    # Trigger async backfill (last 90 days)
    import asyncio
    asyncio.create_task(trigger_strava_backfill(str(athlete.id)))

    return RedirectResponse(f"{settings.FRONTEND_URL}/dashboard?strava=connected")


# ── Garmin OAuth ──────────────────────────────────────────────────────────────

@router.get("/garmin")
async def garmin_oauth_redirect(athlete: Annotated[Athlete, Depends(get_current_athlete)]):
    """Redirect to Garmin OAuth. Returns pending message if creds not configured."""
    if not settings.GARMIN_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="Garmin credentials not configured. Approval may be pending.",
            headers={"X-Garmin-Status": "pending"},
        )
    # Garmin OAuth URL — simplified; actual URL depends on Garmin Connect developer portal
    raise HTTPException(status_code=501, detail="Garmin OAuth not yet implemented")


@router.post("/webhooks/strava")
async def strava_webhook(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    """Strava webhook event handler."""
    # Subscription validation challenge
    params = dict(request.query_params)
    if "hub.challenge" in params:
        return {"hub.challenge": params["hub.challenge"]}

    body = await request.json()
    event_type = body.get("object_type")
    aspect_type = body.get("aspect_type")
    object_id = body.get("object_id")
    owner_id = body.get("owner_id")

    if event_type == "activity" and aspect_type == "create" and object_id:
        from services.sync_service import sync_single_strava_activity
        import asyncio
        asyncio.create_task(sync_single_strava_activity(str(owner_id), int(object_id)))

    return {"status": "ok"}
