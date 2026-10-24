"""
Reset the athlete's login password (there is no "forgot password" flow).

Usage:
    cd backend
    .venv/Scripts/python ../scripts/reset_password.py      # Windows
    .venv/bin/python ../scripts/reset_password.py          # macOS / Linux

Environment:
    Reads DATABASE_URL from backend/.env. Prompts for the new password
    without echoing it.
"""

import asyncio
import getpass
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


async def reset(password: str):
    async with AsyncSessionLocal() as db:
        athletes = (await db.execute(select(Athlete))).scalars().all()
        if len(athletes) != 1:
            print(f"Expected exactly one athlete, found {len(athletes)} — run scripts/seed.py first")
            return

        athlete = athletes[0]
        athlete.hashed_password = hash_password(password)
        await db.commit()
        print(f"Password updated for {athlete.email}")


if __name__ == "__main__":
    password = getpass.getpass("New password: ")
    if len(password) < 8:
        sys.exit("Password must be at least 8 characters")
    if getpass.getpass("Repeat: ") != password:
        sys.exit("Passwords don't match")
    asyncio.run(reset(password))
