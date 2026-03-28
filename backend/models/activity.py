import uuid
from datetime import datetime

from sqlalchemy import String, Integer, Float, DateTime, Boolean, Text, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = (UniqueConstraint("source", "external_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    athlete_id: Mapped[str] = mapped_column(String, ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False)

    source: Mapped[str] = mapped_column(String, nullable=False)          # 'strava' | 'garmin'
    external_id: Mapped[str | None] = mapped_column(String)

    activity_type: Mapped[str] = mapped_column(String, nullable=False)   # 'run' | 'ride' | etc.
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    distance_meters: Mapped[float | None] = mapped_column(Float)
    elevation_gain_meters: Mapped[float | None] = mapped_column(Float)

    avg_hr: Mapped[int | None] = mapped_column(Integer)
    max_hr: Mapped[int | None] = mapped_column(Integer)
    avg_pace_seconds_per_km: Mapped[float | None] = mapped_column(Float)
    avg_cadence: Mapped[int | None] = mapped_column(Integer)
    avg_power: Mapped[int | None] = mapped_column(Integer)

    hr_zone_distribution: Mapped[dict | None] = mapped_column(JSONB)    # {z1: 0.15, z2: 0.30, ...}
    splits: Mapped[list | None] = mapped_column(JSONB)                  # per-km split data

    workout_type: Mapped[str | None] = mapped_column(String)            # 'easy' | 'tempo' | 'long_run' | 'interval' | 'race'
    perceived_effort: Mapped[int | None] = mapped_column(Integer)       # 1–10 RPE
    notes: Mapped[str | None] = mapped_column(Text)
    gear_id: Mapped[str | None] = mapped_column(String)

    # Original API payload — for debugging only; AI layer never reads this
    raw_metadata: Mapped[dict | None] = mapped_column(JSONB)

    athlete: Mapped["Athlete"] = relationship(back_populates="activities")
    embedding: Mapped["ActivityEmbedding | None"] = relationship(back_populates="activity", uselist=False, cascade="all, delete-orphan")
