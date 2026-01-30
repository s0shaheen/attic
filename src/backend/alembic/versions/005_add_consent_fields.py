"""2-2.7: Add consent fields to uploads table.

Revision ID: 005_add_consent_fields
Revises: 004_add_validation_fields
Create Date: 2026-01-30

Adds consent tracking fields to the uploads table:
- consent_given: Boolean flag for explicit consent
- consent_version: Version of consent text shown
- consent_at: Timestamp when consent was recorded

Also adds a constraint to ensure consent_version is set when consent_given is true.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005_add_consent_fields"
down_revision: str = "004_add_validation_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add consent fields to uploads table
    op.add_column(
        "uploads",
        sa.Column("consent_given", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "uploads",
        sa.Column("consent_version", sa.String(20), nullable=True),
    )
    op.add_column(
        "uploads",
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Add constraint: consent_version required if consent_given is true
    op.execute(
        """
        ALTER TABLE uploads
        ADD CONSTRAINT consent_version_required
        CHECK (consent_given = FALSE OR consent_version IS NOT NULL)
        """
    )


def downgrade() -> None:
    # Drop constraint first
    op.execute("ALTER TABLE uploads DROP CONSTRAINT IF EXISTS consent_version_required")

    # Drop columns
    op.drop_column("uploads", "consent_at")
    op.drop_column("uploads", "consent_version")
    op.drop_column("uploads", "consent_given")
