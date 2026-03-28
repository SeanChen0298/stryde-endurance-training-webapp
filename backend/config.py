from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str

    # NOTE: No GEMINI_API_KEY here — each user provides their own via the Settings page.
    # The key is stored AES-256 encrypted in the athletes table.
    GEMINI_ENCRYPTION_KEY: str  # 32-byte hex key: python -c "import secrets; print(secrets.token_hex(32))"
    GEMINI_PRIMARY_MODEL: str = "gemini-2.5-flash"
    GEMINI_FAST_MODEL: str = "gemini-2.5-flash-lite"

    STRAVA_CLIENT_ID: str
    STRAVA_CLIENT_SECRET: str
    STRAVA_WEBHOOK_CALLBACK_URL: str = ""

    GARMIN_CLIENT_ID: str = ""       # optional — app degrades gracefully if empty
    GARMIN_CLIENT_SECRET: str = ""

    GOOGLE_CALENDAR_CLIENT_ID: str = ""
    GOOGLE_CALENDAR_CLIENT_SECRET: str = ""

    JWT_SECRET: str
    JWT_EXPIRE_HOURS: int = 24 * 7   # 7 days

    FRONTEND_URL: str = "http://localhost:3001"
    # Comma-separated list of allowed CORS origins.
    # In production set to your Vercel URL, e.g.: https://stryde.vercel.app
    ALLOWED_ORIGINS: str = "http://localhost:3001"

    ATHLETE_TIMEZONE: str = "Asia/Kuala_Lumpur"
    OPEN_METEO_BASE_URL: str = "https://api.open-meteo.com/v1"

    class Config:
        env_file = ".env"


settings = Settings()
