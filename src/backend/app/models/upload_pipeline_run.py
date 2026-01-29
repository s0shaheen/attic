"""SQLAlchemy UploadPipelineRun model matching PRD schema."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UploadPipelineRun(Base):
    """Processing pipeline run tracking for Supabase Realtime updates.

    Each upload can have multiple pipeline runs (e.g., on retry).
    Used by Supabase Realtime to broadcast progress to the frontend.
    Tracks processing of all media types (videos, images, slideshows).
    """

    __tablename__ = "upload_pipeline_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    upload_id: Mapped[UUID] = mapped_column(
        ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), server_default="pending"
    )  # 'pending', 'processing', 'complete', 'failed'
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Progress tracking (media-agnostic naming for videos/images/slideshows)
    total_items: Mapped[int | None] = mapped_column(Integer)
    items_enriched: Mapped[int] = mapped_column(Integer, server_default="0")
    items_media_downloaded: Mapped[int] = mapped_column(Integer, server_default="0")
    items_transcribed: Mapped[int] = mapped_column(Integer, server_default="0")
    items_vision_done: Mapped[int] = mapped_column(Integer, server_default="0")
    items_embedded: Mapped[int] = mapped_column(Integer, server_default="0")
    items_complete: Mapped[int] = mapped_column(Integer, server_default="0")
    items_failed: Mapped[int] = mapped_column(Integer, server_default="0")

    total_cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4), server_default="0")
    estimated_completion_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_summary: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    upload = relationship("Upload", back_populates="pipeline_runs")
    user = relationship("User", back_populates="pipeline_runs")

    __table_args__ = ({"comment": "Pipeline run tracking for Supabase Realtime progress updates"},)
