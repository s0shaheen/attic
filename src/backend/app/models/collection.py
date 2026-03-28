"""SQLAlchemy models for collections and collection items.

Collections support three creation modes:
- manual: user creates in UI, adds items by hand
- agent: saved from agent query results (linked to conversation)
- import: imported from platform export, e.g. Instagram saved folders (linked to upload)
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Collection(Base):
    """User-curated group of media events."""

    __tablename__ = "collections"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text())
    source_type: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="manual"
    )  # manual | agent | import

    # Mode 2: Agent-created — links to the conversation that produced the results
    conversation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL")
    )
    # Mode 3: Imported — links to the upload that sourced the collection
    upload_id: Mapped[UUID | None] = mapped_column(ForeignKey("uploads.id", ondelete="SET NULL"))
    source_platform: Mapped[str | None] = mapped_column(String(30))  # instagram, etc.
    original_collection_id: Mapped[str | None] = mapped_column(
        String(255)
    )  # Platform's collection ID for re-sync

    cover_image_url: Mapped[str | None] = mapped_column(Text())
    item_count: Mapped[int] = mapped_column(Integer(), nullable=False, server_default="0")
    collection_metadata: Mapped[dict | None] = mapped_column(
        "metadata", JSONB()
    )  # Column name is "metadata" in DB, attribute name avoids SQLAlchemy reserved word

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="collections")
    conversation = relationship("Conversation")
    upload = relationship("Upload")
    items: Mapped[list["CollectionItem"]] = relationship(
        back_populates="collection", cascade="all, delete", order_by="CollectionItem.position"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_collections_user_name"),
        CheckConstraint(
            "source_type IN ('manual', 'agent', 'import')",
            name="ck_collections_source_type",
        ),
        {"comment": "User-curated groups of media events (manual, agent-created, or imported)"},
    )


class CollectionItem(Base):
    """Many-to-many join between collections and media events."""

    __tablename__ = "collection_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    collection_id: Mapped[UUID] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), nullable=False
    )
    media_event_id: Mapped[UUID] = mapped_column(
        ForeignKey("media_events.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer(), nullable=False, server_default="0")
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    collection: Mapped[Collection] = relationship(back_populates="items")
    media_event = relationship("MediaEvent")

    __table_args__ = (
        UniqueConstraint(
            "collection_id", "media_event_id", name="uq_collection_items_collection_media"
        ),
        {"comment": "Many-to-many join between collections and media events"},
    )
