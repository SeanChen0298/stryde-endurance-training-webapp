import uuid
from datetime import date

from sqlalchemy import String, Float, Boolean, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Gear(Base):
    __tablename__ = "gear"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    athlete_id: Mapped[str] = mapped_column(String, ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False)

    strava_gear_id: Mapped[str | None] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    brand: Mapped[str | None] = mapped_column(String)
    model: Mapped[str | None] = mapped_column(String)

    distance_meters: Mapped[float] = mapped_column(Float, default=0.0)
    max_distance_meters: Mapped[float] = mapped_column(Float, default=800_000.0)  # 800km default

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    purchased_at: Mapped[date | None] = mapped_column(Date)
    retired_at: Mapped[date | None] = mapped_column(Date)

    athlete: Mapped["Athlete"] = relationship(back_populates="gear")
