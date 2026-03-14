"""SQLAlchemy MediaEvent model matching PRD schema."""

from datetime import datetime
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import MediaType


class MediaEvent(Base):
    """Media event model representing a TikTok media interaction.

    This is the core entity storing enriched media metadata, AI analysis,
    and search vectors. Supports videos, images, and slideshows.
    """

    __tablename__ = "media_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    upload_id: Mapped[UUID] = mapped_column(
        ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False
    )

    # Source identifiers
    platform: Mapped[str] = mapped_column(String(50), server_default="tiktok")
    platform_id: Mapped[str] = mapped_column(String(255), nullable=False)  # TikTok's video ID
    canonical_url: Mapped[str | None] = mapped_column(Text)
    interaction_type: Mapped[str | None] = mapped_column(String(50))  # 'liked', 'favorited'
    interaction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Processing state
    processing_state: Mapped[str] = mapped_column(String(50), server_default="pending")
    processing_substate: Mapped[str | None] = mapped_column(String(100))

    # From Apify enrichment
    caption_text: Mapped[str | None] = mapped_column(Text)
    hashtags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    mentions: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    creator_username: Mapped[str | None] = mapped_column(String(255))
    creator_name: Mapped[str | None] = mapped_column(String(255))
    creator_id: Mapped[str | None] = mapped_column(String(255))
    creator_followers: Mapped[int | None] = mapped_column(Integer)
    creator_verified: Mapped[bool | None] = mapped_column(Boolean)
    play_count: Mapped[int | None] = mapped_column(BigInteger)
    like_count: Mapped[int | None] = mapped_column(BigInteger)
    comment_count: Mapped[int | None] = mapped_column(BigInteger)
    share_count: Mapped[int | None] = mapped_column(BigInteger)
    collect_count: Mapped[int | None] = mapped_column(BigInteger)
    video_duration_seconds: Mapped[int | None] = mapped_column(Integer)
    video_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_ad: Mapped[bool | None] = mapped_column(Boolean)
    is_pinned: Mapped[bool | None] = mapped_column(Boolean)
    is_slideshow: Mapped[bool | None] = mapped_column(Boolean)

    # Media type classification (added for multi-media support)
    media_type: Mapped[str] = mapped_column(String(20), server_default=MediaType.VIDEO.value)
    image_count: Mapped[int | None] = mapped_column(Integer)
    image_urls: Mapped[list[str] | None] = mapped_column(ARRAY(Text))

    location_created: Mapped[str | None] = mapped_column(String(100))
    music_id: Mapped[str | None] = mapped_column(String(255))
    music_name: Mapped[str | None] = mapped_column(String(255))
    music_author: Mapped[str | None] = mapped_column(String(255))
    music_is_original: Mapped[bool | None] = mapped_column(Boolean)
    effect_stickers: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    thumbnail_url: Mapped[str | None] = mapped_column(Text)

    # From transcription
    subtitle_text: Mapped[str | None] = mapped_column(Text)
    subtitle_source: Mapped[str | None] = mapped_column(String(50))  # 'apify', 'whisper', null

    # From GPT-5.1 Vision
    visual_tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    ocr_text: Mapped[str | None] = mapped_column(Text)

    # Distribution fields (JSONB for full distribution)
    mood_distribution: Mapped[dict | None] = mapped_column(JSONB)  # {"funny": 0.7, ...}
    mood_primary: Mapped[str | None] = mapped_column(String(50))
    mood_primary_confidence: Mapped[float | None] = mapped_column(Float)

    content_category_distribution: Mapped[dict | None] = mapped_column(JSONB)
    content_category_primary: Mapped[str | None] = mapped_column(String(50))
    content_category_primary_confidence: Mapped[float | None] = mapped_column(Float)

    creator_archetype_distribution: Mapped[dict | None] = mapped_column(JSONB)
    creator_archetype_primary: Mapped[str | None] = mapped_column(String(50))
    creator_archetype_primary_confidence: Mapped[float | None] = mapped_column(Float)

    audience_role_distribution: Mapped[dict | None] = mapped_column(JSONB)
    audience_role_primary: Mapped[str | None] = mapped_column(String(50))
    audience_role_primary_confidence: Mapped[float | None] = mapped_column(Float)

    # Single-value fields with confidence
    is_satire: Mapped[bool | None] = mapped_column(Boolean)
    satire_confidence: Mapped[float | None] = mapped_column(Float)

    setting: Mapped[str | None] = mapped_column(String(100))
    setting_confidence: Mapped[float | None] = mapped_column(Float)

    aesthetic_style: Mapped[str | None] = mapped_column(String(100))
    aesthetic_style_confidence: Mapped[float | None] = mapped_column(Float)

    content_format: Mapped[str | None] = mapped_column(String(100))
    content_format_confidence: Mapped[float | None] = mapped_column(Float)

    meme_format: Mapped[str | None] = mapped_column(String(100))
    meme_format_confidence: Mapped[float | None] = mapped_column(Float)

    apparent_intent: Mapped[str | None] = mapped_column(Text)

    # Typed entities (JSONB array)
    entities: Mapped[list | None] = mapped_column(
        JSONB
    )  # [{"surface": "Atomic Habits", "type": "book", ...}]

    # Agent cache (JSONB, GIN-indexed — written by agent tools)
    cached_classifications: Mapped[dict | None] = mapped_column(JSONB)
    cached_entities: Mapped[list | None] = mapped_column(JSONB)

    # Derived fields
    engagement_rate: Mapped[float | None] = mapped_column(Float)
    interaction_hour: Mapped[int | None] = mapped_column(Integer)  # 0-23
    interaction_day_of_week: Mapped[int | None] = mapped_column(Integer)  # 0-6
    creator_is_repeat: Mapped[bool | None] = mapped_column(Boolean)
    hashtag_count: Mapped[int | None] = mapped_column(Integer)
    caption_length: Mapped[int | None] = mapped_column(Integer)
    inferred_user_role: Mapped[str | None] = mapped_column(
        String(50)
    )  # 'wind_down', 'learning', etc.

    # For search
    full_text: Mapped[str | None] = mapped_column(Text)  # Fused searchable text
    embedding_vector = mapped_column(Vector(1536))  # pgvector 1536-dim

    # Future clustering (nullable for MVP)
    cluster_id: Mapped[UUID | None] = mapped_column()

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="media_events")
    upload = relationship("Upload", back_populates="media_events")
    processing_steps = relationship(
        "ProcessingStep", back_populates="media_event", cascade="all, delete"
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id", "platform", "platform_id", name="uq_media_events_user_platform"
        ),
        Index("idx_media_events_user", "user_id"),
        Index("idx_media_events_upload", "upload_id"),
        Index("idx_media_events_platform_id", "platform_id"),
        Index(
            "idx_media_events_processing",
            "processing_state",
            postgresql_where=("processing_state != 'complete'"),
        ),
        Index("idx_media_events_creator", "creator_username"),
        Index("idx_media_events_mood", "mood_primary"),
        Index("idx_media_events_interaction", "interaction_at"),
        Index("idx_media_events_media_type", "media_type"),
        {"comment": "TikTok media interactions with enrichment data"},
    )
