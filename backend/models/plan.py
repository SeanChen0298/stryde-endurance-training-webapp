import uuid
from datetime import date, datetime

from sqlalchemy import String, Integer, Float, Date, DateTime, Boolean, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class TrainingPlan(Base):
    __tablename__ = "training_plans"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    athlete_id: Mapped[str] = mapped_column(String, ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date] = mapped_column(Date, nullable=False)
    goal_race_type: Mapped[str | None] = mapped_column(String)
    goal_race_date: Mapped[date | None] = mapped_column(Date)
    goal_time_seconds: Mapped[int | None] = mapped_column(Integer)

    status: Mapped[str] = mapped_column(String, default="active")       # 'active' | 'superseded' | 'completed'
    plan_summary: Mapped[str | None] = mapped_column(Text)              # AI narrative
    revision_reason: Mapped[str | None] = mapped_column(Text)
    weekly_structure: Mapped[dict | None] = mapped_column(JSONB)

    athlete: Mapped["Athlete"] = relationship(back_populates="training_plans")
    workouts: Mapped[list["PlannedWorkout"]] = relationship(back_populates="plan", cascade="all, delete-orphan")


class PlannedWorkout(Base):
    __tablename__ = "planned_workouts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id: Mapped[str] = mapped_column(String, ForeignKey("training_plans.id", ondelete="CASCADE"), nullable=False)
    athlete_id: Mapped[str] = mapped_column(String, ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False)

    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    workout_type: Mapped[str] = mapped_column(String, nullable=False)   # 'easy' | 'long_run' | 'tempo' | 'interval' | 'rest' | 'race'
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    target_distance_meters: Mapped[float | None] = mapped_column(Float)
    target_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    target_pace_min_seconds_per_km: Mapped[float | None] = mapped_column(Float)
    target_pace_max_seconds_per_km: Mapped[float | None] = mapped_column(Float)
    target_hr_zone: Mapped[int | None] = mapped_column(Integer)        # 1–5
    target_rpe: Mapped[int | None] = mapped_column(Integer)            # 1–10
    intensity_points: Mapped[float | None] = mapped_column(Float)      # TSS equivalent

    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_activity_id: Mapped[str | None] = mapped_column(String, ForeignKey("activities.id"))
    calendar_event_id: Mapped[str | None] = mapped_column(String)      # Google Calendar event ID
    garmin_workout_id: Mapped[str | None] = mapped_column(String)      # Garmin Training API workout ID

    plan: Mapped["TrainingPlan"] = relationship(back_populates="workouts")
