"""
Garmin Connect client using python-garminconnect (garth SSO).

No developer API approval required — uses the athlete's own Garmin Connect
email/password, authenticated via garth OAuth. Tokens are stored AES-256
encrypted on the athletes table and auto-refreshed by garth.

All sync functions are wrapped in run_in_executor (garminconnect is sync).
"""
import asyncio
import functools
import json
import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)


# ── Sync helpers (run in thread pool) ─────────────────────────────────────────

def _login_sync(email: str, password: str, mfa_code: str | None = None) -> str:
    """
    Log in to Garmin Connect and return the garth tokens as a JSON string.
    Uses cloudscraper to bypass Cloudflare protection on sso.garmin.com.
    Raises ValueError on bad credentials/MFA, RuntimeError on other errors.
    """
    import cloudscraper
    import garth
    from garth.exc import GarthException

    try:
        scraper = cloudscraper.create_scraper()
        client = garth.Client(session=scraper)

        # client.login() stores tokens on the client AND supports return_on_mfa
        result = client.login(email, password, return_on_mfa=True)

        if isinstance(result, tuple) and result[0] == "needs_mfa":
            if not mfa_code:
                raise ValueError("Garmin account has MFA enabled — provide your 6-digit code")
            _, state = result
            garth.sso.resume_login(
                client=state["client"],
                signin_params=state["signin_params"],
                mfa_code=mfa_code,
            )
            # After resume_login, tokens are set on state["client"]
            return state["client"].dumps()

        return client.dumps()   # JSON string of OAuth1 + OAuth2 tokens

    except ValueError:
        raise
    except GarthException as exc:
        err = str(exc).lower()
        if "429" in err or "too many" in err or "rate" in err or "locked" in err or "temporarily" in err:
            raise RuntimeError("RATE_LIMITED") from exc
        if "invalid" in err or "incorrect" in err or "unauthorized" in err or "password" in err:
            raise ValueError("Invalid Garmin email or password") from exc
        raise RuntimeError(f"Garmin login failed: {exc}") from exc
    except Exception as exc:
        err = str(exc).lower()
        if "429" in err or "too many" in err or "rate limit" in err or "temporarily" in err or "locked" in err:
            raise RuntimeError("RATE_LIMITED") from exc
        if "mfa" in err or "2fa" in err or "two-factor" in err:
            raise ValueError("Garmin account has MFA enabled — provide your 6-digit code") from exc
        raise RuntimeError(f"Garmin login failed: {exc}") from exc


def _fetch_health_sync(tokens_json: str, for_date: date) -> dict:
    """
    Fetch all health data for a single date.
    Returns a dict with keys: stats, sleep, hrv, rhr.
    """
    from garminconnect import Garmin
    import garth

    garth_client = garth.Client()
    garth_client.loads(tokens_json)

    # Hydrate profile cache — garminconnect uses garth.profile["displayName"] in API URLs.
    # Without this, most endpoints get a malformed URL and return empty/error responses.
    try:
        display_name = garth_client.profile.get("displayName", "")
    except Exception as e:
        logger.warning(f"Could not fetch Garmin profile (display_name will be empty): {e}")
        display_name = ""

    client = Garmin()
    client.garth = garth_client
    client.display_name = display_name

    date_str = for_date.isoformat()
    result = {}

    try:
        result["stats"] = client.get_stats(date_str)
    except Exception as e:
        logger.warning(f"Garmin stats fetch failed for {date_str}: {e}")
        result["stats"] = {}

    try:
        result["sleep"] = client.get_sleep_data(date_str)
    except Exception as e:
        logger.warning(f"Garmin sleep fetch failed for {date_str}: {e}")
        result["sleep"] = {}

    try:
        result["hrv"] = client.get_hrv_data(date_str)
    except Exception as e:
        logger.warning(f"Garmin HRV fetch failed for {date_str}: {e}")
        result["hrv"] = {}

    try:
        result["rhr"] = client.get_rhr_day(date_str)
    except Exception as e:
        logger.warning(f"Garmin RHR fetch failed for {date_str}: {e}")
        result["rhr"] = {}

    # Persist any refreshed tokens
    result["_tokens"] = garth_client.dumps()
    return result


def _fetch_activities_sync(tokens_json: str, start: date, end: date) -> list[dict]:
    """Fetch Garmin activity summaries for a date range."""
    from garminconnect import Garmin
    import garth

    garth_client = garth.Client()
    garth_client.loads(tokens_json)
    try:
        display_name = garth_client.profile.get("displayName", "")
    except Exception:
        display_name = ""
    client = Garmin()
    client.garth = garth_client
    client.display_name = display_name

    try:
        activities = client.get_activities_by_date(start.isoformat(), end.isoformat())
        return activities or []
    except Exception as e:
        logger.warning(f"Garmin activities fetch failed: {e}")
        return []


# ── Async public interface ─────────────────────────────────────────────────────

async def garmin_login(email: str, password: str, mfa_code: str | None = None) -> str:
    """
    Log in and return garth tokens JSON string.
    Raises ValueError on bad credentials/MFA, RuntimeError on other errors.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, functools.partial(_login_sync, email, password, mfa_code)
    )


async def fetch_health_day(tokens_json: str, for_date: date) -> dict:
    """Fetch all health data for a single date. Returns raw data dict."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, functools.partial(_fetch_health_sync, tokens_json, for_date)
    )


async def fetch_activities(tokens_json: str, start: date, end: date) -> list[dict]:
    """Fetch Garmin activity summaries for a date range."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, functools.partial(_fetch_activities_sync, tokens_json, start, end)
    )


# ── Token helpers ──────────────────────────────────────────────────────────────

async def get_valid_garmin_tokens(athlete_id: str, db) -> str | None:
    """
    Return decrypted garth tokens JSON for an athlete, or None if not connected.
    Also persists any token refresh that happened during the last fetch.
    """
    from sqlalchemy import select
    from models.athlete import Athlete
    from utils.encryption import decrypt_api_key

    result = await db.execute(select(Athlete).where(Athlete.id == athlete_id))
    athlete = result.scalar_one_or_none()
    if not athlete or not athlete.garmin_tokens_encrypted:
        return None

    try:
        return decrypt_api_key(athlete.garmin_tokens_encrypted)
    except Exception as exc:
        logger.error(f"Failed to decrypt Garmin tokens for athlete {athlete_id}: {exc}")
        return None


async def save_refreshed_tokens(athlete_id: str, tokens_json: str, db) -> None:
    """Persist refreshed garth tokens back to the database."""
    from sqlalchemy import select
    from models.athlete import Athlete
    from utils.encryption import encrypt_api_key

    result = await db.execute(select(Athlete).where(Athlete.id == athlete_id))
    athlete = result.scalar_one_or_none()
    if athlete:
        athlete.garmin_tokens_encrypted = encrypt_api_key(tokens_json)
        await db.commit()
