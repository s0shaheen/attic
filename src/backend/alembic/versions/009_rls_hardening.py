"""Harden RLS policies with explicit per-operation policies.

Revision ID: 009_rls_hardening
Revises: 008_add_collections
Create Date: 2026-03-28

Replaces coarse FOR ALL USING policies on user-owned tables with explicit
SELECT, INSERT, UPDATE, DELETE policies. Adds WITH CHECK on INSERT/UPDATE
to prevent user_id tampering.

Transitive tables (processing_steps, messages, collection_items) keep their
existing FOR ALL USING(subquery) policies — the parent table's RLS enforces
the user_id check.

Read-only tables (prompt_templates, cost_models) keep their existing
FOR SELECT policies.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "009_rls_hardening"
down_revision: str = "008_add_collections"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables with direct user_id column (or id for users table)
_USER_OWNED_TABLES = {
    "users": "id",  # users.id = auth.uid()
    "uploads": "user_id",
    "upload_pipeline_runs": "user_id",
    "media_events": "user_id",
    "conversations": "user_id",
    "collections": "user_id",
}

# Original policy names to drop
_OLD_POLICIES = {
    "users": "users_own_data",
    "uploads": "uploads_own_data",
    "upload_pipeline_runs": "pipeline_runs_own_data",
    "media_events": "media_events_own_data",
    "conversations": "conversations_user_isolation",
    "collections": "collections_user_isolation",
}


def upgrade() -> None:
    # --- User-owned tables: replace FOR ALL with per-operation policies ---
    for table, col in _USER_OWNED_TABLES.items():
        old_policy = _OLD_POLICIES[table]

        # Drop old FOR ALL policy
        op.execute(f"DROP POLICY IF EXISTS {old_policy} ON {table}")

        # CREATE per-operation policies
        op.execute(f"CREATE POLICY {table}_select ON {table} FOR SELECT USING (auth.uid() = {col})")
        op.execute(
            f"CREATE POLICY {table}_insert ON {table} FOR INSERT WITH CHECK (auth.uid() = {col})"
        )
        op.execute(
            f"CREATE POLICY {table}_update ON {table} "
            f"FOR UPDATE USING (auth.uid() = {col}) "
            f"WITH CHECK (auth.uid() = {col})"
        )
        op.execute(f"CREATE POLICY {table}_delete ON {table} FOR DELETE USING (auth.uid() = {col})")

    # Transitive and read-only tables: no changes needed
    # - processing_steps: FOR ALL USING (EXISTS subquery) — already correct
    # - messages: FOR ALL USING (conversation_id IN subquery) — already correct
    # - collection_items: FOR ALL USING (collection_id IN subquery) — already correct
    # - prompt_templates: FOR SELECT USING (auth.role() = 'authenticated') — already correct
    # - cost_models: FOR SELECT USING (auth.role() = 'authenticated') — already correct


def downgrade() -> None:
    # Restore original FOR ALL policies
    for table, col in _USER_OWNED_TABLES.items():
        # Drop the 4 per-operation policies
        for op_type in ["select", "insert", "update", "delete"]:
            op.execute(f"DROP POLICY IF EXISTS {table}_{op_type} ON {table}")

        # Recreate the original FOR ALL policy
        old_policy = _OLD_POLICIES[table]
        op.execute(f"CREATE POLICY {old_policy} ON {table} FOR ALL USING (auth.uid() = {col})")
