#!/usr/bin/env python
"""Seed the database with real Apify test data + Tier 1 classifications.

Loads the 106-item golden set template (real TikTok metadata from Apify) and
existing Tier 1 classification results into the database, so the agent has
real data to query against.

Usage:
    python workbench/experiments/05-agent-eval/seed_from_apify.py
    python workbench/experiments/05-agent-eval/seed_from_apify.py --limit 47
    python workbench/experiments/05-agent-eval/seed_from_apify.py --skip-embeddings

Requires: Supabase reachable, src/backend/.env configured, OPENAI_API_KEY for embeddings
Idempotent: safe to run multiple times (upserts by platform ID).
"""

import asyncio
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src" / "backend"))

from dotenv import load_dotenv

load_dotenv(REPO_ROOT / "src" / "backend" / ".env")

import httpx
import numpy as np
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.media_event import MediaEvent
from app.models.upload import Upload
from app.models.upload_pipeline_run import UploadPipelineRun
from app.models.user import User
from app.services.ontology import validate_classification

# Data paths
GOLDEN_SET_TEMPLATE = (
    REPO_ROOT / "workbench" / "experiments" / "04-golden-set" / "results" / "golden_set_template.json"
)
APIFY_GOLDEN_SET = (
    REPO_ROOT / "workbench" / "experiments" / "04-golden-set" / "results" / "apify_golden_set_output.json"
)
TIER1_RESULTS_DIR = (
    REPO_ROOT / "workbench" / "experiments" / "03-pipeline-v3" / "results" / "tier1" / "results"
)
SUBTITLES_PATH = (
    REPO_ROOT / "workbench" / "experiments" / "04-golden-set" / "results" / "golden_set_subtitles.json"
)

# Fixed test IDs (same as seed_db.py for compatibility)
TEST_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
TEST_UPLOAD_ID = UUID("00000000-0000-0000-0000-000000000010")  # Different from seed_db
TEST_PIPELINE_RUN_ID = UUID("00000000-0000-0000-0000-000000000011")
TEST_EMAIL = "test@attic.to"

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


def _embed_batch(texts: list[str]) -> list[list[float]]:
    """Call OpenAI embeddings API."""
    resp = httpx.post(
        "https://api.openai.com/v1/embeddings",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"input": texts, "model": EMBEDDING_MODEL, "dimensions": EMBEDDING_DIMENSIONS},
        timeout=120,
    )
    resp.raise_for_status()
    sorted_data = sorted(resp.json()["data"], key=lambda d: d["index"])
    return [d["embedding"] for d in sorted_data]


def _random_vectors(count: int) -> list[list[float]]:
    """Random unit vectors for dev mode (no OpenAI key)."""
    vecs = []
    for _ in range(count):
        v = np.random.randn(EMBEDDING_DIMENSIONS).astype(np.float32)
        v = v / np.linalg.norm(v)
        vecs.append(v.tolist())
    return vecs


def load_golden_set() -> list[dict]:
    """Load golden set template items."""
    return json.loads(GOLDEN_SET_TEMPLATE.read_text())


def load_apify_data() -> dict[str, dict]:
    """Load full Apify output keyed by item ID."""
    items = json.loads(APIFY_GOLDEN_SET.read_text())
    by_id: dict[str, dict] = {}
    for item in items:
        item_id = str(item.get("id", ""))
        if item_id:
            by_id[item_id] = item
    return by_id


def load_tier1_result(item_id: str) -> dict | None:
    """Load Tier 1 classification result for an item."""
    path = TIER1_RESULTS_DIR / f"{item_id}.json"
    if path.exists():
        return json.loads(path.read_text())
    return None


def load_subtitles() -> dict[str, str]:
    """Load subtitle texts keyed by item ID."""
    if SUBTITLES_PATH.exists():
        return json.loads(SUBTITLES_PATH.read_text())
    return {}


def build_classification_cache(tier1_result: dict) -> dict | None:
    """Convert Tier 1 result into cached_classifications format."""
    parsed = tier1_result.get("parsed_output")
    if not parsed:
        return None

    # validate_classification handles primary/dominant key formats
    validated = validate_classification(parsed)

    cache = {
        "tier1": validated.tier1,
        "tier2": validated.tier2,
        "confidence": validated.confidence,
        "source": "pipeline_tier1",
    }
    if parsed.get("summary"):
        cache["summary"] = parsed["summary"]
    if parsed.get("entities"):
        cache["entities"] = parsed["entities"]
    if parsed.get("embedding_text"):
        cache["embedding_text"] = parsed["embedding_text"]
    return cache


def build_media_event(
    gs_item: dict,
    apify_data: dict | None,
    tier1_result: dict | None,
    subtitles: dict,
    user_id: UUID,
    upload_id: UUID,
    index: int,
) -> dict:
    """Build a MediaEvent dict from golden set + Apify + Tier 1 data."""
    item_id = str(gs_item["id"])
    apify = gs_item.get("apify", {})
    full_apify = apify_data or {}

    # Extract Apify metadata
    author = full_apify.get("authorMeta", {})
    music = full_apify.get("musicMeta", {})
    video_meta = full_apify.get("videoMeta", {})
    covers = full_apify.get("covers", {})

    # Media type
    is_slideshow = apify.get("is_slideshow", False)
    image_count = apify.get("image_count")
    if is_slideshow:
        media_type = "slideshow" if (image_count or 0) > 1 else "image"
    else:
        media_type = "video"

    # Hashtags
    raw_hashtags = apify.get("hashtags") or []
    if isinstance(raw_hashtags, list) and raw_hashtags and isinstance(raw_hashtags[0], dict):
        hashtags = [h.get("name", "") for h in raw_hashtags]
    else:
        hashtags = raw_hashtags

    # Caption
    caption = apify.get("caption") or full_apify.get("text") or ""

    # Subtitle
    subtitle_text = subtitles.get(item_id) or apify.get("subtitle_text")

    # Classification
    classification = None
    embedding_text = None
    if tier1_result:
        classification = build_classification_cache(tier1_result)
        if classification:
            embedding_text = classification.get("embedding_text")

    # Build full_text for embedding
    full_text_parts = []
    if embedding_text:
        full_text_parts.append(embedding_text)
    else:
        if caption:
            full_text_parts.append(caption)
        if hashtags:
            full_text_parts.append(" ".join(f"#{h}" for h in hashtags))
        if subtitle_text:
            full_text_parts.append(subtitle_text)
    full_text = " | ".join(full_text_parts) if full_text_parts else "untitled tiktok"

    # Deterministic event ID
    event_id = UUID(f"20000000-0000-0000-0000-{index:012d}")

    create_time = full_apify.get("createTime")
    video_created_at = (
        datetime.fromtimestamp(int(create_time), tz=UTC) if create_time else None
    )

    return {
        "id": event_id,
        "user_id": user_id,
        "upload_id": upload_id,
        "platform": "tiktok",
        "platform_id": item_id,
        "canonical_url": gs_item.get("url") or full_apify.get("webVideoUrl", ""),
        "interaction_type": "favorited",
        "interaction_at": video_created_at or datetime.now(UTC) - timedelta(days=index),
        "processing_state": "complete",
        "caption_text": caption or None,
        "hashtags": hashtags or None,
        "subtitle_text": subtitle_text,
        "creator_username": gs_item.get("creator") or author.get("name"),
        "creator_name": author.get("nickName"),
        "creator_id": str(author.get("id", "")) or None,
        "creator_followers": author.get("fans"),
        "creator_verified": author.get("verified"),
        "play_count": full_apify.get("playCount"),
        "like_count": full_apify.get("diggCount"),
        "comment_count": full_apify.get("commentCount"),
        "share_count": full_apify.get("shareCount"),
        "collect_count": full_apify.get("collectCount"),
        "video_duration_seconds": apify.get("duration_seconds") or video_meta.get("duration"),
        "video_created_at": video_created_at,
        "media_type": media_type,
        "is_slideshow": is_slideshow,
        "image_count": image_count,
        "thumbnail_url": apify.get("thumbnail_url") or covers.get("default"),
        "music_name": music.get("musicName"),
        "music_author": music.get("musicAuthor"),
        "music_is_original": music.get("musicOriginal"),
        "cached_classifications": classification,
        "full_text": full_text,
    }


async def main() -> None:
    # Parse args
    limit = None
    skip_embeddings = "--skip-embeddings" in sys.argv
    for i, arg in enumerate(sys.argv):
        if arg == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set. Run ./scripts/setup-env.sh first.")
        sys.exit(1)

    # Load all data sources
    print("Loading test data...")
    gs_items = load_golden_set()
    apify_by_id = load_apify_data()
    subtitles = load_subtitles()

    if limit:
        gs_items = gs_items[:limit]

    print(f"  Golden set: {len(gs_items)} items")
    print(f"  Apify data: {len(apify_by_id)} items")
    print(f"  Subtitles: {len(subtitles)} items")

    # Count available Tier 1 results
    tier1_count = sum(1 for item in gs_items if load_tier1_result(str(item["id"])))
    print(f"  Tier 1 results: {tier1_count}/{len(gs_items)}")

    # Connect to DB
    connect_args = {}
    if "pooler.supabase.com" in database_url or ":6543/" in database_url:
        connect_args["statement_cache_size"] = 0

    engine = create_async_engine(database_url, echo=False, connect_args=connect_args)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print("\nSeeding database with real Apify test data...")

    async with async_session() as session:
        # Ensure test user exists
        existing_user = await session.execute(select(User).where(User.email == TEST_EMAIL))
        user = existing_user.scalar_one_or_none()
        if user:
            user_id = user.id
            print(f"  User exists: {user_id}")
        else:
            print("  ERROR: Test user not found. Run seed_db.py first.")
            print("    .venv/bin/python workbench/tools/seed_db.py")
            sys.exit(1)

        # Create upload for this test set
        existing_upload = await session.execute(
            select(Upload).where(Upload.id == TEST_UPLOAD_ID)
        )
        if not existing_upload.scalar_one_or_none():
            upload = Upload(
                id=TEST_UPLOAD_ID,
                user_id=user_id,
                source_platform="tiktok",
                scope="favorited",
                status="complete",
                total_items=len(gs_items),
                processed_items=len(gs_items),
                consent_given=True,
                consent_version="1.0",
                consent_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )
            session.add(upload)
            await session.flush()
            print("  Created upload for golden set")
        else:
            print("  Upload already exists")

        # Create pipeline run
        existing_run = await session.execute(
            select(UploadPipelineRun).where(UploadPipelineRun.id == TEST_PIPELINE_RUN_ID)
        )
        if not existing_run.scalar_one_or_none():
            run = UploadPipelineRun(
                id=TEST_PIPELINE_RUN_ID,
                upload_id=TEST_UPLOAD_ID,
                user_id=user_id,
                status="complete",
                total_items=len(gs_items),
                items_enriched=len(gs_items),
                items_transcribed=len(gs_items),
                items_embedded=len(gs_items),
                items_complete=len(gs_items),
                started_at=datetime.now(UTC) - timedelta(hours=1),
                finished_at=datetime.now(UTC),
            )
            session.add(run)
            await session.flush()
            print("  Created pipeline run")

        # Upsert media events
        created = 0
        skipped = 0
        classified = 0

        for i, gs_item in enumerate(gs_items):
            item_id = str(gs_item["id"])
            apify_data = apify_by_id.get(item_id)
            tier1_result = load_tier1_result(item_id)

            event_data = build_media_event(
                gs_item, apify_data, tier1_result, subtitles, user_id, TEST_UPLOAD_ID, i,
            )
            event_id = event_data.pop("id")

            existing = await session.execute(
                select(MediaEvent).where(MediaEvent.id == event_id)
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue

            event = MediaEvent(id=event_id, **event_data)
            session.add(event)
            created += 1
            if event_data.get("cached_classifications"):
                classified += 1

            if (i + 1) % 20 == 0:
                print(f"  [{i + 1}/{len(gs_items)}] processed...")

        await session.commit()
        print(f"\n  Created: {created}, Skipped: {skipped}, Classified: {classified}")

        # Generate embeddings
        if skip_embeddings:
            print("\n  Skipping embeddings (--skip-embeddings)")
        else:
            # Get items without embeddings
            result = await session.execute(
                select(MediaEvent).where(
                    MediaEvent.upload_id == TEST_UPLOAD_ID,
                    MediaEvent.embedding_vector.is_(None),
                    MediaEvent.full_text.isnot(None),
                )
            )
            to_embed = result.scalars().all()

            if not to_embed:
                print("\n  All items already have embeddings")
            elif OPENAI_API_KEY:
                print(f"\n  Generating embeddings for {len(to_embed)} items...")
                texts = [e.full_text or "untitled" for e in to_embed]
                batch_size = 50
                for i in range(0, len(texts), batch_size):
                    batch_texts = texts[i : i + batch_size]
                    batch_events = to_embed[i : i + batch_size]
                    vectors = _embed_batch(batch_texts)
                    for event, vec in zip(batch_events, vectors):
                        event.embedding_vector = vec
                    print(f"    Embedded {min(i + batch_size, len(texts))}/{len(texts)}")
                await session.commit()
                print("  Embeddings complete")
            else:
                print(f"\n  Using random embeddings (no OPENAI_API_KEY) for {len(to_embed)} items")
                vectors = _random_vectors(len(to_embed))
                for event, vec in zip(to_embed, vectors):
                    event.embedding_vector = vec
                await session.commit()
                print("  Random embeddings written")

    await engine.dispose()

    # Summary
    print(f"\nSeed complete!")
    print(f"  Items: {len(gs_items)} golden set items from real Apify data")
    print(f"  Classifications: {tier1_count} items have Tier 1 results")
    print(f"  User: {TEST_EMAIL} / testpassword123")
    print(f"  Upload: {TEST_UPLOAD_ID}")
    print(f"\nReady for agent eval:")
    print(f"  .venv/bin/python workbench/experiments/05-agent-eval/run_agent_eval.py")


if __name__ == "__main__":
    asyncio.run(main())
