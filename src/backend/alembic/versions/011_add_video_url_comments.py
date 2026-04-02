"""Add video_url and comments_top columns to media_events.

Revision ID: 011_add_video_url_comments
Revises: 010_remove_auto_source_type
Create Date: 2026-03-31

Supports pipeline v2: video upload to Gemini requires download URLs,
and comments are now passed to perception prompts.
"""

import sqlalchemy as sa

from alembic import op

revision = "011_add_video_url_comments"
down_revision = "010_remove_auto_source_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("media_events", sa.Column("video_url", sa.Text(), nullable=True))
    op.add_column(
        "media_events",
        sa.Column("comments_top", sa.ARRAY(sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("media_events", "comments_top")
    op.drop_column("media_events", "video_url")
