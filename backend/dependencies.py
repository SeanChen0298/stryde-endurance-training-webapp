from functools import lru_cache
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from config import Settings, settings
from database import get_db


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


@lru_cache
def get_settings() -> Settings:
    return Settings()


async def get_redis() -> aioredis.Redis:
    client = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


async def get_current_athlete(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from utils.jwt import decode_jwt
    from models.athlete import Athlete
    from sqlalchemy import select

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Try Authorization header first, fall back to httpOnly cookie
    token: str | None = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer "):]
    else:
        cookie_value = request.cookies.get("access_token")
        if cookie_value and cookie_value.startswith("Bearer "):
            token = cookie_value[len("Bearer "):]

    if not token:
        raise credentials_exception

    payload = decode_jwt(token)
    if payload is None:
        raise credentials_exception

    athlete_id: str = payload.get("sub")
    if athlete_id is None:
        raise credentials_exception

    result = await db.execute(select(Athlete).where(Athlete.id == athlete_id))
    athlete = result.scalar_one_or_none()
    if athlete is None:
        raise credentials_exception

    return athlete
