"""SQLAlchemy Upload model matching PRD schema."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Upload(Base):
    """User data export upload model.

    Represents a TikTok data export ZIP file uploaded by a user.
    """

    __tablename__ = "uploads"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_platform: Mapped[str] = mapped_column(String(50), server_default="tiktok")
    scope: Mapped[str] = mapped_column(String(50), nullable=False)  # 'liked', 'favorited', 'both'
    status: Mapped[str] = mapped_column(
        String(50), server_default="pending"
    )  # 'pending', 'processing', 'complete', 'failed'
    total_items: Mapped[int | None] = mapped_column(Integer)
    processed_items: Mapped[int] = mapped_column(Integer, server_default="0")
    file_hash: Mapped[str | None] = mapped_column(String(64))  # for debugging, not content
    step_functions_execution_arn: Mapped[str | None] = mapped_column(
        String(255)
    )  # AWS Step Functions execution reference
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    user = relationship("User", back_populates="uploads")
    pipeline_runs = relationship(
        "UploadPipelineRun", back_populates="upload", cascade="all, delete"
    )
    media_events = relationship("MediaEvent", back_populates="upload", cascade="all, delete")

    __table_args__ = ({"comment": "TikTok data export uploads"},)
