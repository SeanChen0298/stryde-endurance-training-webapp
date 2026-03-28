import uuid
from datetime import datetime

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class ActivityEmbedding(Base):
    __tablename__ = "activity_embeddings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    activity_id: Mapped[str] = mapped_column(String, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False)
    athlete_id: Mapped[str] = mapped_column(String, ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False)

    content: Mapped[str] = mapped_column(Text, nullable=False)   # human-readable summary as RAG chunk
    # embedding VECTOR(384) — added via raw SQL in migration (pgvector type not natively in SQLAlchemy)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    activity: Mapped["Activity"] = relationship(back_populates="embedding")


class KnowledgeEmbedding(Base):
    __tablename__ = "knowledge_embeddings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source: Mapped[str | None] = mapped_column(String)          # 'daniels_running_formula' | 'polarised_training' | etc.
    chunk_index: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # embedding VECTOR(384) — added via raw SQL in migration
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
