"""Rename step_functions_execution_arn to pipeline_execution_ref.

Revision ID: 012_rename_step_functions_arn
Revises: 011_add_video_url_comments
Create Date: 2026-04-03

The architecture uses SQS + single Lambda (not Step Functions).
Renames the column to reflect what it actually stores.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "012_rename_step_functions_arn"
down_revision: str = "011_add_video_url_comments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "uploads",
        "step_functions_execution_arn",
        new_column_name="pipeline_execution_ref",
    )


def downgrade() -> None:
    op.alter_column(
        "uploads",
        "pipeline_execution_ref",
        new_column_name="step_functions_execution_arn",
    )
