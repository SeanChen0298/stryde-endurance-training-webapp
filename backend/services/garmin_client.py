"""
Garmin Connect client using python-garminconnect (0.3.x).

No developer API approval required — uses the athlete's own Garmin Connect
account. garminconnect 0.3 signs in with Garmin's mobile SSO and issues its own
token set (di_token / di_refresh_token / di_client_id). The old garth library
and its token format are no longer supported by garminconnect, so tokens saved
before this change must be replaced by signing in again.

Tokens are stored AES-256-GCM encrypted on the athletes table and refreshed by
garminconnect when they are close to expiry.

garminconnect is synchronous, so every network call runs in a worker thread.
One sync run opens ONE client and reuses it for every day/activity it fetches,
instead of signing in again per call.
"""
import asyncio
import functools
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Callable

logger = logging.getLogger(__name__)

MFA_PENDING_TTL_SECONDS = 300


class GarminReconnectRequired(Exception):
    """Stored tokens are missing, unreadable, or in the retired garth format."""


# ── Token format ───────────────────────────────────────────────────────────────

def is_current_token_format(tokens_json: str | None) -> bool:
    """
    True if tokens_json is a garminconnect 0.3 token dump.

    garminconnect 0.3 writes JSON with a 'di_token' key. The retired garth
    format was a base64 blob (not JSON), so it fails this check.
    """
    if not tokens_json:
        return False
    try:
        data = json.loads(tokens_json)
    except (TypeError, ValueError):
        return False
    return isinstance(data, dict) and bool(data.get("di_token")) and bool(data.get("di_refresh_token"))


# ── Client construction (runs in a worker thread) ─────────────────────────────

def _open_client(tokens_json: str):
    """
    Build a signed-in Garmin client from stored tokens.
    Refreshes the token when it is near expiry and loads the profile
    (display name is needed by most health endpoints).
    """
    from garminconnect import Garmin

    if not is_current_token_format(tokens_json):
        raise GarminReconnectRequired("Saved Garmin sign-in is in an old format — sign in again")

    client = Garmin()
    try:
        client.login(tokenstore=tokens_json)
    except Exception as exc:
        raise GarminReconnectRequired(f"Saved Garmin sign-in was rejected — sign in again ({type(exc).__name__})") from exc
    return client


def _dump_tokens(client) -> str:
    return client.client.dumps()


# ── Sign-in with MFA support ──────────────────────────────────────────────────

@dataclass
class _PendingMfa:
    client: Any
    created_at: float = field(default_factory=time.monotonic)

    def expired(self) -> bool:
        return time.monotonic() - self.created_at > MFA_PENDING_TTL_SECONDS


_pending_mfa: dict[str, _PendingMfa] = {}
_pending_lock = threading.Lock()


def _classify_login_error(exc: Exception) -> Exception:
    """Map garminconnect errors to ValueError (user fixable) / RuntimeError."""
    from garminconnect import GarminConnectAuthenticationError, GarminConnectTooManyRequestsError

    if isinstance(exc, GarminConnectTooManyRequestsError):
        return RuntimeError("RATE_LIMITED")
    if isinstance(exc, GarminConnectAuthenticationError):
        return ValueError("Invalid Garmin email or password")
    err = str(exc).lower()
    if "429" in err or "too many" in err or "rate limit" in err:
        return RuntimeError("RATE_LIMITED")
    return RuntimeError(f"Garmin login failed: {type(exc).__name__}")


def _login_sync(email: str, password: str, mfa_code: str | None = None, garmin_factory: Callable | None = None) -> str:
    """
    Sign in to Garmin Connect and return the token JSON string.

    MFA: the first call (no code) starts the sign-in, Garmin sends a code, and
    the half-finished sign-in is kept in memory for 5 minutes. The second call
    with the code finishes that same sign-in. This avoids starting a fresh
    sign-in (which would send a new code and invalidate the first).

    Raises ValueError on bad credentials or when an MFA code is needed,
    RuntimeError("RATE_LIMITED") or RuntimeError on other failures.
    """
    if garmin_factory is None:
        from garminconnect import Garmin as garmin_factory  # noqa: N813

    key = email.strip().lower()

    if mfa_code:
        with _pending_lock:
            pending = _pending_mfa.pop(key, None)
        if pending and not pending.expired():
            try:
                pending.client.resume_login({}, mfa_code.strip())
                return _dump_tokens(pending.client)
            except Exception as exc:
                raise _classify_login_error(exc) from exc

    client = garmin_factory(email, password, return_on_mfa=True)
    try:
        status, _ = client.login()
    except Exception as exc:
        raise _classify_login_error(exc) from exc

    if status == "needs_mfa":
        if mfa_code:
            # No pending sign-in survived (server restart or expiry): finish
            # this fresh one with the code we were given.
            try:
                client.resume_login({}, mfa_code.strip())
                return _dump_tokens(client)
            except Exception as exc:
                raise _classify_login_error(exc) from exc
        with _pending_lock:
            _pending_mfa[key] = _PendingMfa(client=client)
        raise ValueError("Garmin account has MFA enabled — enter the 6-digit code Garmin just sent you")

    return _dump_tokens(client)


# ── Fetching (runs in a worker thread, one client per run) ────────────────────

def _fetch_health_for_client(client, for_date: date) -> dict:
    """Fetch stats, sleep, HRV and resting HR for one date with an open client."""
    date_str = for_date.isoformat()
    result: dict[str, Any] = {}

    calls = {
        "stats": client.get_stats,
        "sleep": client.get_sleep_data,
        "hrv": client.get_hrv_data,
        "rhr": client.get_rhr_day,
    }
    for key, fn in calls.items():
        try:
            result[key] = fn(date_str) or {}
        except Exception as e:
            logger.warning(f"Garmin {key} fetch failed for {date_str}: {type(e).__name__}: {e}")
            result[key] = {}
            if key == "hrv":
                result["_hrv_error"] = f"{type(e).__name__}: {e}"
    return result


def _fetch_health_range_sync(tokens_json: str, start: date, end: date, open_client: Callable = _open_client) -> tuple[dict[date, dict], str]:
    """Fetch health data for every date in [start, end]. Returns (by_date, refreshed_tokens)."""
    client = open_client(tokens_json)
    out: dict[date, dict] = {}
    day = start
    while day <= end:
        out[day] = _fetch_health_for_client(client, day)
        day += timedelta(days=1)
    return out, _dump_tokens(client)


def _fetch_activities_sync(tokens_json: str, start: date, end: date, open_client: Callable = _open_client) -> tuple[list[dict], str]:
    """Fetch activity summaries between two dates (inclusive). Returns (activities, refreshed_tokens)."""
    client = open_client(tokens_json)
    activities = client.get_activities_by_date(start.isoformat(), end.isoformat()) or []
    return activities, _dump_tokens(client)


# ── Async public interface ─────────────────────────────────────────────────────

async def _run(fn, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, functools.partial(fn, *args))


async def garmin_login(email: str, password: str, mfa_code: str | None = None) -> str:
    """Sign in and return token JSON. See _login_sync for errors."""
    return await _run(_login_sync, email, password, mfa_code)


async def validate_tokens(tokens_json: str) -> str:
    """Open a client with pasted tokens to prove they work. Returns refreshed tokens."""
    def _validate(tj: str) -> str:
        return _dump_tokens(_open_client(tj))
    return await _run(_validate, tokens_json)


async def fetch_health_day(tokens_json: str, for_date: date) -> dict:
    """Fetch all health data for a single date (used by the debug endpoint)."""
    by_date, refreshed = await _run(_fetch_health_range_sync, tokens_json, for_date, for_date)
    result = by_date[for_date]
    result["_tokens"] = refreshed
    return result


async def fetch_health_range(tokens_json: str, start: date, end: date) -> tuple[dict[date, dict], str]:
    return await _run(_fetch_health_range_sync, tokens_json, start, end)


async def fetch_activities(tokens_json: str, start: date, end: date) -> tuple[list[dict], str]:
    return await _run(_fetch_activities_sync, tokens_json, start, end)


# ── Token helpers ──────────────────────────────────────────────────────────────

async def get_valid_garmin_tokens(athlete_id: str, db) -> str | None:
    """
    Return decrypted token JSON for an athlete, or None if not connected
    or if the saved tokens are in the retired garth format.
    """
    from sqlalchemy import select
    from models.athlete import Athlete
    from utils.encryption import decrypt_api_key

    result = await db.execute(select(Athlete).where(Athlete.id == athlete_id))
    athlete = result.scalar_one_or_none()
    if not athlete or not athlete.garmin_tokens_encrypted:
        return None

    try:
        tokens_json = decrypt_api_key(athlete.garmin_tokens_encrypted)
    except Exception as exc:
        logger.error(f"Failed to decrypt Garmin tokens for athlete {athlete_id}: {exc}")
        return None

    if not is_current_token_format(tokens_json):
        logger.warning(f"Garmin tokens for athlete {athlete_id} are in the old garth format — reconnect needed")
        return None
    return tokens_json


async def save_refreshed_tokens(athlete_id: str, tokens_json: str, db) -> None:
    """Persist refreshed tokens back to the database."""
    from sqlalchemy import select
    from models.athlete import Athlete
    from utils.encryption import encrypt_api_key

    result = await db.execute(select(Athlete).where(Athlete.id == athlete_id))
    athlete = result.scalar_one_or_none()
    if athlete:
        athlete.garmin_tokens_encrypted = encrypt_api_key(tokens_json)
        await db.commit()
