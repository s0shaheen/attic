"""Add media_type field and image-related columns to media_events.

Revision ID: 002_add_media_type
Revises: 001_initial_schema
Create Date: 2026-01-28

Adds multi-media support:
- media_type: VARCHAR(20) to classify content as video/image/slideshow
- image_count: INT for slideshow frame count
- image_urls: TEXT[] for slideshow image URLs
- Backfills existing is_slideshow=true rows to media_type='slideshow'
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_add_media_type"
down_revision: str = "001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add media_type column with default 'video'
    op.add_column(
        "media_events",
        sa.Column("media_type", sa.String(20), server_default="video", nullable=False),
    )

    # Add image-related columns for slideshows
    op.add_column(
        "media_events",
        sa.Column("image_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "media_events",
        sa.Column("image_urls", postgresql.ARRAY(sa.Text()), nullable=True),
    )

    # Create index for media_type queries
    op.create_index("idx_media_events_media_type", "media_events", ["media_type"])

    # Backfill: set media_type='slideshow' where is_slideshow=true
    op.execute(
        """
        UPDATE media_events
        SET media_type = 'slideshow'
        WHERE is_slideshow = true
        """
    )


def downgrade() -> None:
    op.drop_index("idx_media_events_media_type", table_name="media_events")
    op.drop_column("media_events", "image_urls")
    op.drop_column("media_events", "image_count")
    op.drop_column("media_events", "media_type")
