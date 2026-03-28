"""Add collections and collection_items tables.

Revision ID: 008_add_collections
Revises: 007_nullable_scope
Create Date: 2026-03-28

Adds:
- collections table: user-curated groups of media events
  Supports three creation modes: manual, agent-driven, imported (Instagram)
- collection_items table: many-to-many join between collections and media_events
- RLS policies for both tables
- Indexes for efficient querying
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "008_add_collections"
down_revision: str = "007_nullable_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- collections table ---
    op.create_table(
        "collections",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "source_type",
            sa.String(30),
            nullable=False,
            server_default="manual",
        ),  # manual | agent | import
        sa.Column(
            "conversation_id",
            sa.UUID(),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "upload_id",
            sa.UUID(),
            sa.ForeignKey("uploads.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_platform", sa.String(30), nullable=True),  # instagram, etc.
        sa.Column(
            "original_collection_id", sa.String(255), nullable=True
        ),  # IG collection ID for re-sync
        sa.Column("cover_image_url", sa.Text(), nullable=True),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata", sa.dialects.postgresql.JSONB(), nullable=True),
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
        sa.UniqueConstraint("user_id", "name", name="uq_collections_user_name"),
        sa.CheckConstraint(
            "source_type IN ('manual', 'agent', 'import')",
            name="ck_collections_source_type",
        ),
        comment="User-curated groups of media events (manual, agent-created, or imported)",
    )
    op.create_index("idx_collections_user_id", "collections", ["user_id"])
    op.create_index("idx_collections_conversation_id", "collections", ["conversation_id"])
    op.create_index("idx_collections_upload_id", "collections", ["upload_id"])

    # --- collection_items table ---
    op.create_table(
        "collection_items",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "collection_id",
            sa.UUID(),
            sa.ForeignKey("collections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "media_event_id",
            sa.UUID(),
            sa.ForeignKey("media_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "collection_id",
            "media_event_id",
            name="uq_collection_items_collection_media",
        ),
        comment="Many-to-many join between collections and media events",
    )
    op.create_index("idx_collection_items_collection_id", "collection_items", ["collection_id"])
    op.create_index("idx_collection_items_media_event_id", "collection_items", ["media_event_id"])

    # --- RLS policies ---
    op.execute("ALTER TABLE collections ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY collections_user_isolation ON collections USING (user_id = auth.uid())"
    )

    op.execute("ALTER TABLE collection_items ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY collection_items_via_collection ON collection_items "
        "USING (collection_id IN ("
        "  SELECT id FROM collections WHERE user_id = auth.uid()"
        "))"
    )


def downgrade() -> None:
    # Drop RLS policies
    op.execute("DROP POLICY IF EXISTS collection_items_via_collection ON collection_items")
    op.execute("ALTER TABLE collection_items DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS collections_user_isolation ON collections")
    op.execute("ALTER TABLE collections DISABLE ROW LEVEL SECURITY")

    # Drop tables (collection_items first due to FK)
    op.drop_table("collection_items")
    op.drop_table("collections")
