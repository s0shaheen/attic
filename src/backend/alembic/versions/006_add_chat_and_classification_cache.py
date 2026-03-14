"""Add chat tables and classification cache columns.

Revision ID: 006_add_chat_and_classification_cache
Revises: 005_add_consent_fields
Create Date: 2026-03-14

Adds:
- conversations table: chat session metadata per user
- messages table: individual chat messages (user + assistant)
- cached_classifications JSONB column on media_events (GIN indexed)
- cached_entities JSONB column on media_events (GIN indexed)
- RLS policies for conversations and messages
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006_add_chat_and_classification_cache"
down_revision: str = "005_add_consent_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- conversations table ---
    op.create_table(
        "conversations",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.Text(), nullable=True),
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
        comment="Chat conversations per user",
    )
    op.create_index("idx_conversations_user_id", "conversations", ["user_id"])

    # --- messages table ---
    op.create_table(
        "messages",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "conversation_id",
            sa.UUID(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),  # 'user' | 'assistant'
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_calls", sa.JSON(), nullable=True),  # tool invocations + results
        sa.Column("token_count", sa.Integer(), nullable=True),  # for cost tracking
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        comment="Individual chat messages within conversations",
    )
    op.create_index("idx_messages_conversation_id", "messages", ["conversation_id"])

    # --- cached_classifications + cached_entities on media_events ---
    op.add_column(
        "media_events",
        sa.Column("cached_classifications", sa.dialects.postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "media_events",
        sa.Column("cached_entities", sa.dialects.postgresql.JSONB(), nullable=True),
    )

    # GIN indexes for fast JSONB containment queries (@>)
    op.execute(
        "CREATE INDEX idx_media_events_classifications "
        "ON media_events USING GIN (cached_classifications jsonb_ops)"
    )
    op.execute(
        "CREATE INDEX idx_media_events_entities "
        "ON media_events USING GIN (cached_entities jsonb_ops)"
    )

    # --- RLS policies ---
    op.execute("ALTER TABLE conversations ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY conversations_user_isolation ON conversations USING (user_id = auth.uid())"
    )

    op.execute("ALTER TABLE messages ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY messages_user_isolation ON messages "
        "USING (conversation_id IN ("
        "  SELECT id FROM conversations WHERE user_id = auth.uid()"
        "))"
    )


def downgrade() -> None:
    # Drop RLS policies
    op.execute("DROP POLICY IF EXISTS messages_user_isolation ON messages")
    op.execute("ALTER TABLE messages DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS conversations_user_isolation ON conversations")
    op.execute("ALTER TABLE conversations DISABLE ROW LEVEL SECURITY")

    # Drop GIN indexes
    op.execute("DROP INDEX IF EXISTS idx_media_events_entities")
    op.execute("DROP INDEX IF EXISTS idx_media_events_classifications")

    # Drop columns
    op.drop_column("media_events", "cached_entities")
    op.drop_column("media_events", "cached_classifications")

    # Drop tables (messages first due to FK)
    op.drop_table("messages")
    op.drop_table("conversations")
