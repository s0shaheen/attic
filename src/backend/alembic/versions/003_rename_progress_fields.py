"""Rename video-centric progress fields to media-agnostic terms.

Revision ID: 003_rename_progress_fields
Revises: 002_add_media_type
Create Date: 2026-01-28

Renames upload_pipeline_runs columns:
- total_videos → total_items
- videos_enriched → items_enriched
- videos_media_downloaded → items_media_downloaded
- videos_transcribed → items_transcribed
- videos_vision_done → items_vision_done
- videos_embedded → items_embedded
- videos_complete → items_complete
- videos_failed → items_failed

This enables proper multi-media support (videos, images, slideshows).
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003_rename_progress_fields"
down_revision: str = "002_add_media_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Rename all video-centric columns to media-agnostic names
    op.alter_column(
        "upload_pipeline_runs",
        "total_videos",
        new_column_name="total_items",
    )
    op.alter_column(
        "upload_pipeline_runs",
        "videos_enriched",
        new_column_name="items_enriched",
    )
    op.alter_column(
        "upload_pipeline_runs",
        "videos_media_downloaded",
        new_column_name="items_media_downloaded",
    )
    op.alter_column(
        "upload_pipeline_runs",
        "videos_transcribed",
        new_column_name="items_transcribed",
    )
    op.alter_column(
        "upload_pipeline_runs",
        "videos_vision_done",
        new_column_name="items_vision_done",
    )
    op.alter_column(
        "upload_pipeline_runs",
        "videos_embedded",
        new_column_name="items_embedded",
    )
    op.alter_column(
        "upload_pipeline_runs",
        "videos_complete",
        new_column_name="items_complete",
    )
    op.alter_column(
        "upload_pipeline_runs",
        "videos_failed",
        new_column_name="items_failed",
    )


def downgrade() -> None:
    # Revert to video-centric column names
    op.alter_column(
        "upload_pipeline_runs",
        "total_items",
        new_column_name="total_videos",
    )
    op.alter_column(
        "upload_pipeline_runs",
        "items_enriched",
        new_column_name="videos_enriched",
    )
    op.alter_column(
        "upload_pipeline_runs",
        "items_media_downloaded",
        new_column_name="videos_media_downloaded",
    )
    op.alter_column(
        "upload_pipeline_runs",
        "items_transcribed",
        new_column_name="videos_transcribed",
    )
    op.alter_column(
        "upload_pipeline_runs",
        "items_vision_done",
        new_column_name="videos_vision_done",
    )
    op.alter_column(
        "upload_pipeline_runs",
        "items_embedded",
        new_column_name="videos_embedded",
    )
    op.alter_column(
        "upload_pipeline_runs",
        "items_complete",
        new_column_name="videos_complete",
    )
    op.alter_column(
        "upload_pipeline_runs",
        "items_failed",
        new_column_name="videos_failed",
    )
