"""2-2.5: Add validation fields to uploads table.

Revision ID: 004_add_validation_fields
Revises: 003_rename_progress_fields
Create Date: 2026-01-30

Adds validation tracking fields to the uploads table:
- validation_error: Error code if validation failed
- validation_message: Human-readable error message
- validated_at: Timestamp when validation completed
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004_add_validation_fields"
down_revision: str = "003_rename_progress_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add validation fields to uploads table
    op.add_column("uploads", sa.Column("validation_error", sa.String(50), nullable=True))
    op.add_column("uploads", sa.Column("validation_message", sa.Text(), nullable=True))
    op.add_column(
        "uploads",
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("uploads", "validated_at")
    op.drop_column("uploads", "validation_message")
    op.drop_column("uploads", "validation_error")
