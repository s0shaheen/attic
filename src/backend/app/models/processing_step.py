"""SQLAlchemy ProcessingStep model matching PRD schema."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ProcessingStep(Base):
    """Individual processing step execution record.

    Tracks each step of the pipeline for a media event, including
    cost tracking and error handling.
    """

    __tablename__ = "processing_steps"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    media_event_id: Mapped[UUID] = mapped_column(
        ForeignKey("media_events.id", ondelete="CASCADE"), nullable=False
    )
    step_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'APIFY_ENRICH', 'MEDIA_DOWNLOAD', etc.
    provider: Mapped[str | None] = mapped_column(
        String(100)
    )  # 'apify_clockworks', 'openai_gpt5.1', etc.
    status: Mapped[str] = mapped_column(
        String(20), server_default="pending"
    )  # 'pending', 'running', 'succeeded', 'failed', 'skipped'
    attempt: Mapped[int] = mapped_column(Integer, server_default="1")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    input_summary: Mapped[dict | None] = mapped_column(JSONB)
    output_summary: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    prompt_version: Mapped[str | None] = mapped_column(String(50))  # For LLM steps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    media_event = relationship("MediaEvent", back_populates="processing_steps")

    __table_args__ = (
        UniqueConstraint(
            "media_event_id", "step_type", "attempt", name="uq_processing_steps_media_step_attempt"
        ),
        Index("idx_processing_steps_media", "media_event_id"),
        Index(
            "idx_processing_steps_pending",
            "status",
            postgresql_where=("status IN ('pending', 'running')"),
        ),
        Index("idx_processing_steps_step", "step_type", "status"),
        {"comment": "Per-step processing records for media events"},
    )
