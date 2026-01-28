"""0.4: Initial schema with all core tables.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-01-28

Creates the initial database schema for Attic MVP:
- users: User accounts linked to Supabase Auth
- uploads: TikTok data export uploads
- upload_pipeline_runs: Pipeline run tracking for Supabase Realtime
- media_events: TikTok video interactions with enrichment data
- processing_steps: Per-step processing records
- prompt_templates: Versioned LLM prompt templates
- cost_models: Provider pricing for cost tracking

Also enables required PostgreSQL extensions (vector, pg_trgm),
sets up RLS policies, and seeds initial cost_models data.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable required extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("auth_provider", sa.String(50), nullable=False),
        sa.Column("auth_provider_id", sa.String(255), nullable=False),
        sa.Column("subscription_tier", sa.String(50), server_default="free", nullable=True),
        sa.Column("subscription_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        comment="User accounts linked to Supabase Auth",
    )

    # Create uploads table
    op.create_table(
        "uploads",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("source_platform", sa.String(50), server_default="tiktok", nullable=True),
        sa.Column("scope", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), server_default="pending", nullable=True),
        sa.Column("total_items", sa.Integer(), nullable=True),
        sa.Column("processed_items", sa.Integer(), server_default="0", nullable=True),
        sa.Column("file_hash", sa.String(64), nullable=True),
        sa.Column("step_functions_execution_arn", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="TikTok data export uploads",
    )
    op.create_index("ix_uploads_user_id", "uploads", ["user_id"])

    # Create upload_pipeline_runs table
    op.create_table(
        "upload_pipeline_runs",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("upload_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_videos", sa.Integer(), nullable=True),
        sa.Column("videos_enriched", sa.Integer(), server_default="0", nullable=True),
        sa.Column("videos_media_downloaded", sa.Integer(), server_default="0", nullable=True),
        sa.Column("videos_transcribed", sa.Integer(), server_default="0", nullable=True),
        sa.Column("videos_vision_done", sa.Integer(), server_default="0", nullable=True),
        sa.Column("videos_embedded", sa.Integer(), server_default="0", nullable=True),
        sa.Column("videos_complete", sa.Integer(), server_default="0", nullable=True),
        sa.Column("videos_failed", sa.Integer(), server_default="0", nullable=True),
        sa.Column("total_cost_usd", sa.Numeric(10, 4), server_default="0", nullable=True),
        sa.Column("estimated_completion_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_summary", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["upload_id"], ["uploads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Pipeline run tracking for Supabase Realtime progress updates",
    )
    op.create_index("ix_upload_pipeline_runs_upload_id", "upload_pipeline_runs", ["upload_id"])
    op.create_index("ix_upload_pipeline_runs_user_id", "upload_pipeline_runs", ["user_id"])

    # Create media_events table
    op.create_table(
        "media_events",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("upload_id", sa.UUID(), nullable=False),
        # Source identifiers
        sa.Column("platform", sa.String(50), server_default="tiktok", nullable=True),
        sa.Column("platform_id", sa.String(255), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("interaction_type", sa.String(50), nullable=True),
        sa.Column("interaction_at", sa.DateTime(timezone=True), nullable=True),
        # Processing state
        sa.Column("processing_state", sa.String(50), server_default="pending", nullable=True),
        sa.Column("processing_substate", sa.String(100), nullable=True),
        # From Apify enrichment
        sa.Column("caption_text", sa.Text(), nullable=True),
        sa.Column("hashtags", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("mentions", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("creator_username", sa.String(255), nullable=True),
        sa.Column("creator_name", sa.String(255), nullable=True),
        sa.Column("creator_id", sa.String(255), nullable=True),
        sa.Column("creator_followers", sa.Integer(), nullable=True),
        sa.Column("creator_verified", sa.Boolean(), nullable=True),
        sa.Column("play_count", sa.BigInteger(), nullable=True),
        sa.Column("like_count", sa.BigInteger(), nullable=True),
        sa.Column("comment_count", sa.BigInteger(), nullable=True),
        sa.Column("share_count", sa.BigInteger(), nullable=True),
        sa.Column("collect_count", sa.BigInteger(), nullable=True),
        sa.Column("video_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("video_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_ad", sa.Boolean(), nullable=True),
        sa.Column("is_pinned", sa.Boolean(), nullable=True),
        sa.Column("is_slideshow", sa.Boolean(), nullable=True),
        sa.Column("location_created", sa.String(100), nullable=True),
        sa.Column("music_id", sa.String(255), nullable=True),
        sa.Column("music_name", sa.String(255), nullable=True),
        sa.Column("music_author", sa.String(255), nullable=True),
        sa.Column("music_is_original", sa.Boolean(), nullable=True),
        sa.Column("effect_stickers", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        # From transcription
        sa.Column("subtitle_text", sa.Text(), nullable=True),
        sa.Column("subtitle_source", sa.String(50), nullable=True),
        # From GPT-5.1 Vision
        sa.Column("visual_tags", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        # Distribution fields (JSONB)
        sa.Column("mood_distribution", postgresql.JSONB(), nullable=True),
        sa.Column("mood_primary", sa.String(50), nullable=True),
        sa.Column("mood_primary_confidence", sa.Float(), nullable=True),
        sa.Column("content_category_distribution", postgresql.JSONB(), nullable=True),
        sa.Column("content_category_primary", sa.String(50), nullable=True),
        sa.Column("content_category_primary_confidence", sa.Float(), nullable=True),
        sa.Column("creator_archetype_distribution", postgresql.JSONB(), nullable=True),
        sa.Column("creator_archetype_primary", sa.String(50), nullable=True),
        sa.Column("creator_archetype_primary_confidence", sa.Float(), nullable=True),
        sa.Column("audience_role_distribution", postgresql.JSONB(), nullable=True),
        sa.Column("audience_role_primary", sa.String(50), nullable=True),
        sa.Column("audience_role_primary_confidence", sa.Float(), nullable=True),
        # Single-value fields with confidence
        sa.Column("is_satire", sa.Boolean(), nullable=True),
        sa.Column("satire_confidence", sa.Float(), nullable=True),
        sa.Column("setting", sa.String(100), nullable=True),
        sa.Column("setting_confidence", sa.Float(), nullable=True),
        sa.Column("aesthetic_style", sa.String(100), nullable=True),
        sa.Column("aesthetic_style_confidence", sa.Float(), nullable=True),
        sa.Column("content_format", sa.String(100), nullable=True),
        sa.Column("content_format_confidence", sa.Float(), nullable=True),
        sa.Column("meme_format", sa.String(100), nullable=True),
        sa.Column("meme_format_confidence", sa.Float(), nullable=True),
        sa.Column("apparent_intent", sa.Text(), nullable=True),
        # Typed entities
        sa.Column("entities", postgresql.JSONB(), nullable=True),
        # Derived fields
        sa.Column("engagement_rate", sa.Float(), nullable=True),
        sa.Column("interaction_hour", sa.Integer(), nullable=True),
        sa.Column("interaction_day_of_week", sa.Integer(), nullable=True),
        sa.Column("creator_is_repeat", sa.Boolean(), nullable=True),
        sa.Column("hashtag_count", sa.Integer(), nullable=True),
        sa.Column("caption_length", sa.Integer(), nullable=True),
        sa.Column("inferred_user_role", sa.String(50), nullable=True),
        # For search
        sa.Column("full_text", sa.Text(), nullable=True),
        sa.Column("embedding_vector", Vector(1536), nullable=True),
        # Future clustering
        sa.Column("cluster_id", sa.UUID(), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["upload_id"], ["uploads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "platform", "platform_id", name="uq_media_events_user_platform"
        ),
        comment="TikTok video interactions with enrichment data",
    )
    # Create indexes for media_events
    op.create_index("idx_media_events_user", "media_events", ["user_id"])
    op.create_index("idx_media_events_upload", "media_events", ["upload_id"])
    op.create_index("idx_media_events_platform_id", "media_events", ["platform_id"])
    op.create_index(
        "idx_media_events_processing",
        "media_events",
        ["processing_state"],
        postgresql_where=sa.text("processing_state != 'complete'"),
    )
    op.create_index("idx_media_events_creator", "media_events", ["creator_username"])
    op.create_index("idx_media_events_mood", "media_events", ["mood_primary"])
    op.create_index("idx_media_events_interaction", "media_events", ["interaction_at"])
    # Full-text search index (GIN)
    op.execute(
        """
        CREATE INDEX idx_media_events_fulltext
        ON media_events
        USING GIN (to_tsvector('english', COALESCE(full_text, '')))
        """
    )
    # Vector similarity index (ivfflat) - will be created after data is loaded
    # Note: ivfflat requires data to train; create with lists=100 for production
    op.execute(
        """
        CREATE INDEX idx_media_events_embedding
        ON media_events
        USING ivfflat (embedding_vector vector_cosine_ops)
        WITH (lists = 100)
        """
    )

    # Create processing_steps table
    op.create_table(
        "processing_steps",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("media_event_id", sa.UUID(), nullable=False),
        sa.Column("step_type", sa.String(50), nullable=False),
        sa.Column("provider", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending", nullable=True),
        sa.Column("attempt", sa.Integer(), server_default="1", nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input_summary", postgresql.JSONB(), nullable=True),
        sa.Column("output_summary", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("prompt_version", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["media_event_id"], ["media_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "media_event_id", "step_type", "attempt", name="uq_processing_steps_media_step_attempt"
        ),
        comment="Per-step processing records for media events",
    )
    op.create_index("idx_processing_steps_media", "processing_steps", ["media_event_id"])
    op.create_index(
        "idx_processing_steps_pending",
        "processing_steps",
        ["status"],
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )
    op.create_index("idx_processing_steps_step", "processing_steps", ["step_type", "status"])

    # Create prompt_templates table
    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("temperature", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("user_prompt_template", sa.Text(), nullable=True),
        sa.Column("response_schema", postgresql.JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="false", nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "version", name="uq_prompt_templates_name_version"),
        comment="Versioned LLM prompt templates",
    )

    # Create cost_models table
    op.create_table(
        "cost_models",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("sku", sa.String(100), nullable=False),
        sa.Column("metric", sa.String(50), nullable=False),
        sa.Column("unit_price_usd", sa.Numeric(12, 8), nullable=False),
        sa.Column(
            "effective_from",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "sku", "effective_from", name="uq_cost_models_provider_sku_effective"
        ),
        comment="Provider pricing for cost tracking",
    )

    # Seed cost_models with initial pricing data from PRD
    op.execute(
        """
        INSERT INTO cost_models (provider, sku, metric, unit_price_usd, notes) VALUES
        ('apify', 'clockworks_data_extractor:video', 'videos', 0.002, 'Business tier'),
        ('openai', 'gpt-5.1:input_tokens', 'tokens', 0.00000125, '$1.25/1M'),
        ('openai', 'gpt-5.1:output_tokens', 'tokens', 0.00001, '$10/1M'),
        ('openai', 'text-embedding-3-small:tokens', 'tokens', 0.00000002, '$0.02/1M'),
        ('openai', 'whisper:audio_seconds', 'seconds', 0.0001, '$0.006/min')
        """
    )

    # Enable Row Level Security on all user-owned tables
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE uploads ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE upload_pipeline_runs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE media_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE processing_steps ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE prompt_templates ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE cost_models ENABLE ROW LEVEL SECURITY")

    # Create RLS policies
    # Note: These policies use auth.uid() which is Supabase's function to get current user
    # For backend access (service role), RLS is bypassed

    # Users: users can only see/modify their own row
    op.execute(
        """
        CREATE POLICY users_own_data ON users
        FOR ALL USING (auth.uid() = id)
        """
    )

    # Uploads: users can only access their own uploads
    op.execute(
        """
        CREATE POLICY uploads_own_data ON uploads
        FOR ALL USING (auth.uid() = user_id)
        """
    )

    # Upload pipeline runs: users can only access their own pipeline runs
    op.execute(
        """
        CREATE POLICY pipeline_runs_own_data ON upload_pipeline_runs
        FOR ALL USING (auth.uid() = user_id)
        """
    )

    # Media events: users can only access their own media events
    op.execute(
        """
        CREATE POLICY media_events_own_data ON media_events
        FOR ALL USING (auth.uid() = user_id)
        """
    )

    # Processing steps: accessed via media_event ownership
    op.execute(
        """
        CREATE POLICY processing_steps_via_media_event ON processing_steps
        FOR ALL USING (
            EXISTS (
                SELECT 1 FROM media_events
                WHERE media_events.id = processing_steps.media_event_id
                AND media_events.user_id = auth.uid()
            )
        )
        """
    )

    # Prompt templates: read-only for all authenticated users
    op.execute(
        """
        CREATE POLICY prompt_templates_read ON prompt_templates
        FOR SELECT USING (auth.role() = 'authenticated')
        """
    )

    # Cost models: read-only for all authenticated users
    op.execute(
        """
        CREATE POLICY cost_models_read ON cost_models
        FOR SELECT USING (auth.role() = 'authenticated')
        """
    )


def downgrade() -> None:
    # Drop RLS policies first
    op.execute("DROP POLICY IF EXISTS cost_models_read ON cost_models")
    op.execute("DROP POLICY IF EXISTS prompt_templates_read ON prompt_templates")
    op.execute("DROP POLICY IF EXISTS processing_steps_via_media_event ON processing_steps")
    op.execute("DROP POLICY IF EXISTS media_events_own_data ON media_events")
    op.execute("DROP POLICY IF EXISTS pipeline_runs_own_data ON upload_pipeline_runs")
    op.execute("DROP POLICY IF EXISTS uploads_own_data ON uploads")
    op.execute("DROP POLICY IF EXISTS users_own_data ON users")

    # Drop tables in reverse order (respecting foreign keys)
    op.drop_table("cost_models")
    op.drop_table("prompt_templates")
    op.drop_table("processing_steps")
    op.drop_table("media_events")
    op.drop_table("upload_pipeline_runs")
    op.drop_table("uploads")
    op.drop_table("users")

    # Note: We don't drop the extensions as they may be used by other schemas
