"""SQLAlchemy PromptTemplate model matching PRD schema."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PromptTemplate(Base):
    """LLM prompt template for video analysis.

    Stores versioned prompts for GPT-4 Vision analysis and other LLM steps.
    """

    __tablename__ = "prompt_templates"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # 'video_analysis', 'cluster_labeling'
    version: Mapped[str] = mapped_column(String(20), nullable=False)  # 'v1', 'v2', etc.
    model: Mapped[str] = mapped_column(String(100), nullable=False)  # 'gpt-5.1', 'gpt-4o-mini'
    temperature: Mapped[float] = mapped_column(Float, server_default="0.0")
    max_tokens: Mapped[int | None] = mapped_column(Integer)
    system_prompt: Mapped[str | None] = mapped_column(Text)
    user_prompt_template: Mapped[str | None] = mapped_column(Text)  # With {placeholders}
    response_schema: Mapped[dict | None] = mapped_column(JSONB)  # Expected JSON structure
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_prompt_templates_name_version"),
        {"comment": "Versioned LLM prompt templates"},
    )
