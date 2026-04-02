#!/usr/bin/env python
"""Backfill script: re-process existing items through pipeline v2.

Resets processing_state from 'complete' back to 'subtitled' so that
step_perceive (v2) and step_classify (v2) re-run with the new prompts.
Embeddings are also regenerated since embedding_text changes.

Usage:
    # Dry run — show what would be re-processed
    .venv/bin/python workbench/tools/backfill_v2.py --dry-run

    # Re-process all items for a specific user
    .venv/bin/python workbench/tools/backfill_v2.py --user-id <uuid>

    # Re-process all items (all users)
    .venv/bin/python workbench/tools/backfill_v2.py --all

    # Limit to N items (useful for testing)
    .venv/bin/python workbench/tools/backfill_v2.py --all --limit 50
"""

import argparse
import os
import sys
from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv

# Add backend to path
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src" / "backend"))

load_dotenv(REPO_ROOT / ".env.master")

from sqlalchemy import create_engine, func, select, update  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.models.media_event import MediaEvent  # noqa: E402


def get_engine():
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return create_engine(url, pool_pre_ping=True)


def main():
    parser = argparse.ArgumentParser(description="Backfill items to pipeline v2")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--user-id", type=str, help="UUID of user to backfill")
    group.add_argument("--all", action="store_true", help="Backfill all users")
    group.add_argument("--dry-run", action="store_true", help="Show counts only")
    parser.add_argument("--limit", type=int, default=None, help="Max items to process")
    args = parser.parse_args()

    engine = get_engine()
    session = sessionmaker(engine, expire_on_commit=False)()

    # Count items that would be affected
    query = select(func.count()).where(
        MediaEvent.processing_state == "complete",
    )
    if args.user_id:
        query = query.where(MediaEvent.user_id == UUID(args.user_id))

    total = session.scalar(query) or 0

    # Count items already on v2
    v2_query = select(func.count()).where(
        MediaEvent.processing_state == "complete",
        MediaEvent.cached_classifications.isnot(None),
    )
    if args.user_id:
        v2_query = v2_query.where(MediaEvent.user_id == UUID(args.user_id))

    # Check source field in cached_classifications for v2 items
    print(f"Total complete items: {total}")

    if args.dry_run:
        # Show breakdown
        v1_sources = ["pipeline_tier1", "pipeline_tier1_with_perception", "agent_chat"]
        for source in v1_sources:
            count = session.scalar(
                select(func.count()).where(
                    MediaEvent.processing_state == "complete",
                    MediaEvent.cached_classifications["source"].astext == source,
                )
            ) or 0
            if count:
                print(f"  source={source}: {count}")
        print("\nTo backfill, run with --all or --user-id <uuid>")
        session.close()
        return

    limit = args.limit or total
    print(f"Will reset up to {limit} items from 'complete' → 'subtitled'")
    print("This will re-run: perceive (v2) → classify (v2) → embed")

    confirm = input("Continue? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        session.close()
        return

    # Reset items: complete → subtitled (skips steps 1-3, re-runs 4-6)
    stmt = (
        update(MediaEvent)
        .where(
            MediaEvent.processing_state == "complete",
            *([MediaEvent.user_id == UUID(args.user_id)] if args.user_id else []),
        )
        .values(
            processing_state="subtitled",
            updated_at=func.now(),
        )
    )
    if args.limit:
        # SQLAlchemy doesn't support LIMIT on UPDATE directly, use subquery
        ids_to_update = (
            select(MediaEvent.id)
            .where(
                MediaEvent.processing_state == "complete",
                *([MediaEvent.user_id == UUID(args.user_id)] if args.user_id else []),
            )
            .limit(args.limit)
        )
        stmt = (
            update(MediaEvent)
            .where(MediaEvent.id.in_(ids_to_update))
            .values(
                processing_state="subtitled",
                updated_at=func.now(),
            )
        )

    result = session.execute(stmt)
    session.commit()
    print(f"Reset {result.rowcount} items to 'subtitled' state")
    print("Run the pipeline to re-process them (they'll be picked up automatically)")
    session.close()


if __name__ == "__main__":
    main()
