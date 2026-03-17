"""Make uploads.scope nullable for upload wizard flow.

Revision ID: 007_nullable_scope
Revises: 006_add_chat_and_classification_cache
Create Date: 2026-03-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "007_nullable_scope"
down_revision: str = "006_add_chat_and_classification_cache"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("uploads", "scope", nullable=True)


def downgrade() -> None:
    op.execute("UPDATE uploads SET scope = 'both' WHERE scope IS NULL")
    op.alter_column("uploads", "scope", nullable=False)
