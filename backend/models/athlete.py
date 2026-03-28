import uuid
from datetime import datetime

from sqlalchemy import String, Integer, Date, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Athlete(Base):
    __tablename__ = "athletes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)

    strava_athlete_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    garmin_user_id: Mapped[str | None] = mapped_column(String, unique=True)

    timezone: Mapped[str] = mapped_column(String, default="Asia/Kuala_Lumpur")
    goal_race_type: Mapped[str | None] = mapped_column(String)       # 'half_marathon' | 'marathon'
    goal_race_date: Mapped[datetime | None] = mapped_column(Date)
    goal_finish_time_seconds: Mapped[int | None] = mapped_column(Integer)

    # User-provided Gemini key, AES-256 encrypted. NULL until user sets it.
    gemini_api_key_encrypted: Mapped[str | None] = mapped_column(String)
    gemini_model: Mapped[str] = mapped_column(String, default="gemini-2.5-flash")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    oauth_tokens: Mapped[list["OAuthToken"]] = relationship(back_populates="athlete", cascade="all, delete-orphan")
    activities: Mapped[list["Activity"]] = relationship(back_populates="athlete", cascade="all, delete-orphan")
    health_metrics: Mapped[list["HealthMetrics"]] = relationship(back_populates="athlete", cascade="all, delete-orphan")
    readiness_scores: Mapped[list["ReadinessScore"]] = relationship(back_populates="athlete", cascade="all, delete-orphan")
    training_plans: Mapped[list["TrainingPlan"]] = relationship(back_populates="athlete", cascade="all, delete-orphan")
    gear: Mapped[list["Gear"]] = relationship(back_populates="athlete", cascade="all, delete-orphan")
