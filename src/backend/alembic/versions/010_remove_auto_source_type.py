"""Remove 'auto' from collections source_type and clean up auto-generated collections.

Revision ID: 010_remove_auto_source_type
Revises: 009_rls_hardening
Create Date: 2026-03-30

Auto-collections feature deferred. This migration:
- Deletes all collection_items belonging to auto-generated collections
- Deletes all auto-generated collections
- Reverts the source_type check constraint to ('manual', 'agent', 'import')
"""

from alembic import op

revision = "010_remove_auto_source_type"
down_revision = "009_rls_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Clean up auto-generated data first
    op.execute("""
        DELETE FROM collection_items ci
        USING collections c
        WHERE ci.collection_id = c.id AND c.source_type = 'auto'
    """)
    op.execute("DELETE FROM collections WHERE source_type = 'auto'")

    # Revert check constraint to exclude 'auto'
    op.drop_constraint("ck_collections_source_type", "collections", type_="check")
    op.create_check_constraint(
        "ck_collections_source_type",
        "collections",
        "source_type IN ('manual', 'agent', 'import')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_collections_source_type", "collections", type_="check")
    op.create_check_constraint(
        "ck_collections_source_type",
        "collections",
        "source_type IN ('manual', 'agent', 'import', 'auto')",
    )
