"""SQLAlchemy CostModel model matching PRD schema."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CostModel(Base):
    """Provider pricing model for cost tracking.

    Stores unit pricing for various providers and SKUs to track
    processing costs per step.
    """

    __tablename__ = "cost_models"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    provider: Mapped[str] = mapped_column(String(100), nullable=False)  # 'openai', 'apify'
    sku: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # 'gpt-5.1:input_tokens', 'clockworks:video'
    metric: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'tokens', 'videos', 'gpu_seconds'
    unit_price_usd: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint(
            "provider", "sku", "effective_from", name="uq_cost_models_provider_sku_effective"
        ),
        {"comment": "Provider pricing for cost tracking"},
    )
