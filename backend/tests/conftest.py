"""
Pytest configuration — set required env vars before any test import.
"""
import os
import pytest


def pytest_configure(config):
    """Set minimal env vars needed to import backend modules without a real DB."""
    defaults = {
        "DATABASE_URL": "postgresql+asyncpg://test:test@localhost/test",
        "REDIS_URL": "redis://localhost:6379",
        "GEMINI_ENCRYPTION_KEY": "a" * 64,
        "JWT_SECRET": "test_jwt_secret_for_testing_only",
        "STRAVA_CLIENT_ID": "test_strava_id",
        "STRAVA_CLIENT_SECRET": "test_strava_secret",
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)
