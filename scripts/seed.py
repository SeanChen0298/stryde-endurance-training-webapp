"""
Seed script — run once to create the single athlete user.

Usage:
    cd backend
    python ../scripts/seed.py

Environment:
    Reads DATABASE_URL from backend/.env
"""

import asyncio
import os
import sys

# Add backend/ to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

from database import AsyncSessionLocal
from models.athlete import Athlete
from utils.jwt import hash_password
from sqlalchemy import select


ATHLETE_EMAIL = os.getenv("SEED_EMAIL", "faiz@example.my")
ATHLETE_NAME = os.getenv("SEED_NAME", "Muhammad Faizal")
ATHLETE_PASSWORD = os.getenv("SEED_PASSWORD", "changeme123")
ATHLETE_TIMEZONE = "Asia/Kuala_Lumpur"


async def seed():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Athlete).where(Athlete.email == ATHLETE_EMAIL))
        existing = result.scalar_one_or_none()

        if existing:
            print(f"Athlete already exists: {existing.email} (id={existing.id})")
            return

        athlete = Athlete(
            email=ATHLETE_EMAIL,
            name=ATHLETE_NAME,
            hashed_password=hash_password(ATHLETE_PASSWORD),
            timezone=ATHLETE_TIMEZONE,
            goal_race_type="marathon",
        )
        db.add(athlete)
        await db.commit()
        await db.refresh(athlete)

        print(f"Created athlete: {athlete.email} (id={athlete.id})")
        print(f"  Name:     {athlete.name}")
        print(f"  Timezone: {athlete.timezone}")
        print(f"  Password: {ATHLETE_PASSWORD}  ← change this!")
        print()
        print("Next steps:")
        print("  1. Set SEED_PASSWORD env var to something secure before seeding in production")
        print("  2. Connect Strava via /auth/strava in the app")
        print("  3. Add your Gemini API key via the Settings page")


if __name__ == "__main__":
    asyncio.run(seed())
