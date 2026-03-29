from datetime import date, datetime

from sqlalchemy import String, Integer, Float, Date, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class HealthMetrics(Base):
    __tablename__ = "health_metrics"

    athlete_id: Mapped[str] = mapped_column(String, ForeignKey("athletes.id", ondelete="CASCADE"), primary_key=True)
    recorded_date: Mapped[date] = mapped_column(Date, primary_key=True)

    hrv_rmssd: Mapped[float | None] = mapped_column(Float)              # ms
    hrv_sdrr: Mapped[float | None] = mapped_column(Float)
    resting_hr: Mapped[int | None] = mapped_column(Integer)
    sleep_score: Mapped[int | None] = mapped_column(Integer)            # 0–100 Garmin score
    sleep_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    deep_sleep_minutes: Mapped[int | None] = mapped_column(Integer)
    rem_sleep_minutes: Mapped[int | None] = mapped_column(Integer)
    sleep_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sleep_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    light_sleep_minutes: Mapped[int | None] = mapped_column(Integer)
    awake_count: Mapped[int | None] = mapped_column(Integer)               # wake-ups during sleep
    sleep_stress_avg: Mapped[float | None] = mapped_column(Float)          # avg stress during sleep
    body_battery_at_wake: Mapped[int | None] = mapped_column(Integer)      # BB level at wake time
    sleep_score_insight: Mapped[str | None] = mapped_column(Text)          # e.g. NEGATIVE_LATE_BED_TIME

    body_battery_max: Mapped[int | None] = mapped_column(Integer)
    body_battery_min: Mapped[int | None] = mapped_column(Integer)
    stress_avg: Mapped[int | None] = mapped_column(Integer)
    steps: Mapped[int | None] = mapped_column(Integer)
    spo2_avg: Mapped[float | None] = mapped_column(Float)
    respiratory_rate: Mapped[float | None] = mapped_column(Float)
    training_readiness_score: Mapped[int | None] = mapped_column(Integer)  # Garmin's own composite

    athlete: Mapped["Athlete"] = relationship(back_populates="health_metrics")


class ReadinessScore(Base):
    __tablename__ = "readiness_scores"

    athlete_id: Mapped[str] = mapped_column(String, ForeignKey("athletes.id", ondelete="CASCADE"), primary_key=True)
    score_date: Mapped[date] = mapped_column(Date, primary_key=True)

    readiness_score: Mapped[float | None] = mapped_column(Float)        # 0–100
    hrv_delta_pct: Mapped[float | None] = mapped_column(Float)          # % vs 30-day baseline
    sleep_delta_pct: Mapped[float | None] = mapped_column(Float)
    load_delta_pct: Mapped[float | None] = mapped_column(Float)
    ai_summary: Mapped[str | None] = mapped_column(Text)                # 3-bullet AI readiness brief
    ai_recommendation: Mapped[str | None] = mapped_column(Text)

    athlete: Mapped["Athlete"] = relationship(back_populates="readiness_scores")
