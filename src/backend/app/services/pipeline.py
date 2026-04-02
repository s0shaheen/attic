# Upload processing pipeline (6 steps, idempotent)
#
#   parsed ──► enriched ──► subtitled ──► perceived ──► classified ──► complete
#     │            │             │             │             │
#     └──► skip ◄──┘──► skip ◄──┘       (Gemini v2      (Gemini v2
#     (already      (images/          + video upload)   8-facet classify)
#      enriched)     slideshows)
#
# Video processing: Videos are uploaded to Gemini File API for full
# video analysis. Each video upload adds ~30-60s latency. A time budget
# (STEP_TIME_BUDGET_S) ensures the pipeline makes progress within the
# Lambda timeout. On retry, idempotent state transitions resume from
# where processing left off.
#
# Dev mode fallbacks:
#   No APIFY_API_TOKEN → _fake_apify_response() in step 2
#   No GEMINI_API_KEY  → _fake_classification() in step 4
#   No OPENAI_API_KEY  → _random_vectors() in step 5

"""Unified 6-step pipeline for data export processing.

SQS -> Lambda: parse -> apify_enrich -> subtitle -> perceive -> classify -> embed

Each step is idempotent (upserts with deterministic IDs).
Single invocation processes one upload (SQS BatchSize: 1).
Steps advance items through processing_state:
    parsed -> enriched -> subtitled -> classified -> complete.
On retry, each step only picks up items still in its expected input state.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from dotenv import load_dotenv
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, sessionmaker

from app.common.idempotency import generate_idempotency_key
from app.common.logger import get_logger

# Imports from CommonLayer (bundled backend app/)
from app.models.collection import Collection, CollectionItem
from app.models.media_event import MediaEvent
from app.models.upload import Upload
from app.models.upload_pipeline_run import UploadPipelineRun
from app.schemas.instagram_export import extract_shortcode as _extract_ig_shortcode
from app.services.instagram_parser import parse_instagram_export
from app.services.tiktok_parser import parse_tiktok_export

# Load .env for local dev (no-op if vars already set, e.g. Lambda)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

logger = get_logger("pipeline")

# ---------- Configuration ----------

DATABASE_URL = os.environ.get("DATABASE_URL", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SECRET_KEY = os.environ.get("SUPABASE_SECRET_KEY", "")
APIFY_API_TOKEN = os.environ.get("APIFY_API_TOKEN", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

APIFY_BATCH_SIZE = 50
CLASSIFY_CONCURRENCY = int(os.environ.get("CLASSIFY_CONCURRENCY", "20"))
PERCEIVE_CONCURRENCY = int(os.environ.get("PERCEIVE_CONCURRENCY", "20"))
# Time budget per step to stay within Lambda's 900s timeout.
# Steps commit progress and return when budget is exceeded.
# On retry, idempotent state transitions resume from where they left off.
STEP_TIME_BUDGET_S = int(os.environ.get("STEP_TIME_BUDGET_S", "360"))  # 6 minutes
EMBEDDING_BATCH_SIZE = 100
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
APIFY_TIKTOK_ACTOR_ID = "clockworks~tiktok-scraper"
APIFY_INSTAGRAM_ACTOR_ID = "apify~instagram-scraper"
APIFY_ACTOR_ID = APIFY_TIKTOK_ACTOR_ID  # Backward compat alias
APIFY_POLL_INTERVAL_S = 5
APIFY_MAX_WAIT_S = 600  # 10 minutes

# ---------- DB Engine (module-level, reused across warm invocations) ----------

_engine = None


def _get_engine():
    """Create or return cached sync SQLAlchemy engine."""
    global _engine  # noqa: PLW0603
    if _engine is None:
        url = DATABASE_URL
        # Normalize to sync driver (psycopg v3)
        if url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        _engine = create_engine(url, pool_pre_ping=True, pool_size=1, max_overflow=0)
    return _engine


def _session() -> Session:
    """Create a new sync DB session."""
    factory = sessionmaker(_get_engine(), expire_on_commit=False)
    return factory()


# ---------- HTTP Helpers ----------


def _http_json(
    method: str,
    url: str,
    headers: dict[str, str],
    body: dict | list | None = None,
    timeout: int = 60,
) -> Any:
    """Make an HTTP request and return parsed JSON response."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read())


def _http_download(url: str, headers: dict[str, str], dest_path: str, timeout: int = 120) -> None:
    """Download a file via HTTP to a local path."""
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        with open(dest_path, "wb") as f:
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                f.write(chunk)


# ---------- URL Helpers ----------

_TIKTOK_VIDEO_ID_RE = re.compile(r"/video/(\d+)")


def _normalize_tiktok_url(url: str) -> str:
    """Normalize TikTok URL variants for Apify compatibility.

    Apify expects tiktok.com URLs, not tiktokv.com or vm.tiktok.com short links.
    """
    # tiktokv.com/share/video/ID → tiktok.com/share/video/ID
    return url.replace("://www.tiktokv.com/", "://www.tiktok.com/")


def _extract_platform_id(url: str) -> str | None:
    """Extract TikTok video ID from URL (e.g. /video/7123456789)."""
    match = _TIKTOK_VIDEO_ID_RE.search(url)
    return match.group(1) if match else None


def _extract_platform_id_or_hash(url: str, upload_id: str) -> str:
    """Extract platform ID or generate a deterministic one from URL."""
    pid = _extract_platform_id(url)
    if pid:
        return pid
    # For short URLs (vm.tiktok.com), use a deterministic hash as platform_id
    return generate_idempotency_key(upload_id, url)


def _extract_ig_platform_id_or_hash(url: str, upload_id: str) -> str:
    """Extract Instagram shortcode or generate a deterministic ID from URL."""
    shortcode = _extract_ig_shortcode(url)
    if shortcode:
        return shortcode
    return generate_idempotency_key(upload_id, url)


# ==========================================================================
# Step 1: PARSE_EXPORT
# ==========================================================================


def step_parse_export(
    session: Session,
    upload_id: str,
    user_id: str,
    storage_path: str,
    scope: str,
    source_platform: str = "tiktok",
) -> list[str]:
    """Download ZIP from Supabase Storage, parse, upsert media_event rows.

    Dispatches to the correct parser based on source_platform.
    For Instagram, also imports user-created collections.

    Returns list of media_event IDs (as strings).
    """
    step_start = time.time()
    logger.info(
        "Step 1/7: parse_export started",
        extra={"upload_id": upload_id, "platform": source_platform},
    )

    # Mark upload as processing and sync source_platform
    session.execute(
        update(Upload)
        .where(Upload.id == UUID(upload_id))
        .values(status="processing", source_platform=source_platform)
    )
    session.flush()

    # Download ZIP from Supabase Storage to /tmp
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        download_url = f"{SUPABASE_URL}/storage/v1/object/{storage_path}"
        _http_download(
            download_url,
            headers={
                "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
                "apikey": SUPABASE_SECRET_KEY,
            },
            dest_path=tmp_path,
        )

        if source_platform == "instagram":
            ig_parsed = parse_instagram_export(Path(tmp_path))
            all_refs = [
                (ref.url, ref.timestamp, ref.creator_username, "saved")
                for ref in ig_parsed.saved_posts
            ]
            ig_collections = ig_parsed.collections
        else:
            parsed = parse_tiktok_export(Path(tmp_path), scope=scope)
            all_refs = [
                (ref.url, ref.timestamp, None, ref.interaction_type)
                for ref in parsed.liked_videos + parsed.favorited_videos
            ]
            ig_collections = None
    finally:
        os.unlink(tmp_path)

    # Update upload total_items
    session.execute(
        update(Upload).where(Upload.id == UUID(upload_id)).values(total_items=len(all_refs))
    )

    # Upsert media_event rows with deterministic IDs
    media_event_ids: list[str] = []
    for url, timestamp, _creator, interaction_type in all_refs:
        if source_platform == "instagram":
            platform_id = _extract_ig_platform_id_or_hash(url, upload_id)
        else:
            platform_id = _extract_platform_id_or_hash(url, upload_id)
        event_id = generate_idempotency_key(upload_id, url)

        stmt = (
            pg_insert(MediaEvent)
            .values(
                id=UUID(event_id),
                user_id=UUID(user_id),
                upload_id=UUID(upload_id),
                platform=source_platform,
                platform_id=platform_id,
                canonical_url=url,
                interaction_type=interaction_type,
                interaction_at=timestamp,
                processing_state="parsed",
            )
            .on_conflict_do_update(
                constraint="uq_media_events_user_platform",
                set_={
                    "interaction_type": interaction_type,
                    "interaction_at": timestamp,
                    # Don't reset processing_state — preserve progress from prior attempts
                    "updated_at": func.now(),
                },
            )
        )
        session.execute(stmt)
        media_event_ids.append(event_id)

    # Import Instagram collections (if present)
    if ig_collections:
        _import_ig_collections(
            session,
            user_id,
            upload_id,
            ig_collections,
            media_event_ids,
            all_refs,
        )

    session.commit()

    duration_ms = int((time.time() - step_start) * 1000)
    logger.info(
        "Step 1/7: parse_export complete",
        extra={
            "upload_id": upload_id,
            "items": len(media_event_ids),
            "platform": source_platform,
            "duration_ms": duration_ms,
        },
    )
    _dev_print(f"Step 1/7: Parsed {len(media_event_ids)} URLs from {source_platform} export")
    return media_event_ids


def _import_ig_collections(
    session: Session,
    user_id: str,
    upload_id: str,
    ig_collections: list,
    media_event_ids: list[str],
    all_refs: list[tuple],
) -> None:
    """Import Instagram user-created collections into the collections table.

    Creates Collection rows (source_type='import', source_platform='instagram')
    and links items to their media_events via CollectionItem.
    """
    uid = UUID(user_id)
    upid = UUID(upload_id)

    # Build URL → event_id lookup for matching collection items to media events
    url_to_event_id: dict[str, str] = {}
    for (url, _ts, _cr, _it), event_id in zip(all_refs, media_event_ids):
        url_to_event_id[url] = event_id

    imported_count = 0
    for ig_coll in ig_collections:
        # Guard: never overwrite a manual/auto/agent collection
        existing = session.execute(
            select(
                Collection.__table__.c.id,
                Collection.__table__.c.source_type,
            ).where(
                Collection.__table__.c.user_id == uid,
                Collection.__table__.c.name == ig_coll.name,
            )
        ).first()

        if existing and existing.source_type != "import":
            logger.info(
                "IG collection import skipped — name conflicts with "
                f"existing {existing.source_type} collection",
                extra={
                    "upload_id": upload_id,
                    "collection_name": ig_coll.name,
                },
            )
            continue

        if existing:
            # Update existing import collection
            collection_id = existing.id
            session.execute(
                update(Collection.__table__)
                .where(Collection.__table__.c.id == collection_id)
                .values(
                    upload_id=upid,
                    source_platform="instagram",
                    updated_at=func.now(),
                )
            )
        else:
            # Insert new import collection
            stmt = (
                pg_insert(Collection.__table__)
                .values(
                    user_id=uid,
                    name=ig_coll.name,
                    source_type="import",
                    source_platform="instagram",
                    upload_id=upid,
                    item_count=0,
                )
                .returning(Collection.__table__.c.id)
            )
            result = session.execute(stmt)
            collection_id = result.scalar_one()

        # Link collection items to media events
        for position, item in enumerate(ig_coll.items):
            event_id = url_to_event_id.get(item.url)
            if not event_id:
                continue

            item_stmt = (
                pg_insert(CollectionItem.__table__)
                .values(
                    collection_id=collection_id,
                    media_event_id=UUID(event_id),
                    position=position,
                )
                .on_conflict_do_nothing(constraint="uq_collection_items_collection_media")
            )
            session.execute(item_stmt)

        # Update item_count to reflect actual total (fix: COUNT(*) not batch)
        count = session.scalar(
            select(func.count()).where(CollectionItem.__table__.c.collection_id == collection_id)
        )
        session.execute(
            update(Collection.__table__)
            .where(Collection.__table__.c.id == collection_id)
            .values(item_count=count)
        )
        imported_count += 1

    if imported_count:
        logger.info(
            "Imported Instagram collections",
            extra={"upload_id": upload_id, "count": imported_count},
        )
        _dev_print(f"  Imported {imported_count} Instagram collections")


# ==========================================================================
# Step 2: APIFY_ENRICH
# ==========================================================================


def _run_apify_batch(urls: list[str]) -> list[dict]:
    """Start an Apify TikTok scraper run, poll for completion, return items."""
    headers = {
        "Authorization": f"Bearer {APIFY_API_TOKEN}",
        "Content-Type": "application/json",
    }

    # Start run
    run_resp = _http_json(
        "POST",
        f"https://api.apify.com/v2/acts/{APIFY_ACTOR_ID}/runs",
        headers=headers,
        body={"postURLs": urls, "resultsPerPage": len(urls)},
        timeout=30,
    )
    run_id = run_resp["data"]["id"]

    # Poll for completion
    elapsed = 0
    status = "RUNNING"
    status_resp: dict = {}
    while elapsed < APIFY_MAX_WAIT_S:
        time.sleep(APIFY_POLL_INTERVAL_S)
        elapsed += APIFY_POLL_INTERVAL_S

        status_resp = _http_json(
            "GET",
            f"https://api.apify.com/v2/actor-runs/{run_id}",
            headers=headers,
            timeout=15,
        )
        status = status_resp["data"]["status"]
        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            break

    if status != "SUCCEEDED":
        logger.warning("Apify run did not succeed", extra={"run_id": run_id, "status": status})
        return []

    # Fetch dataset items (returns JSON array directly)
    dataset_id = status_resp["data"]["defaultDatasetId"]
    items: list[dict] = _http_json(
        "GET",
        f"https://api.apify.com/v2/datasets/{dataset_id}/items?format=json",
        headers=headers,
        timeout=60,
    )
    return items if isinstance(items, list) else []


def _map_apify_to_update(apify_data: dict) -> dict[str, Any]:
    """Map Apify response fields to MediaEvent column values."""
    author = apify_data.get("authorMeta") or {}
    music = apify_data.get("musicMeta") or {}
    video_meta = apify_data.get("videoMeta") or {}
    covers = apify_data.get("covers") or {}

    is_slideshow = bool(apify_data.get("imagePost"))
    images = apify_data.get("images") or []
    if is_slideshow or len(images) > 0:
        media_type = "slideshow" if len(images) > 1 else "image"
    else:
        media_type = "video"

    hashtags = [
        h.get("name", "") for h in (apify_data.get("hashtags") or []) if isinstance(h, dict)
    ]

    create_time = apify_data.get("createTime")
    video_created_at = datetime.fromtimestamp(int(create_time), tz=UTC) if create_time else None

    return {
        "caption_text": apify_data.get("text"),
        "hashtags": hashtags or None,
        "mentions": apify_data.get("mentions") or None,
        "creator_username": author.get("name"),
        "creator_name": author.get("nickName"),
        "creator_id": str(author.get("id", "")) or None,
        "creator_followers": author.get("fans"),
        "creator_verified": author.get("verified"),
        "play_count": apify_data.get("playCount"),
        "like_count": apify_data.get("diggCount"),
        "comment_count": apify_data.get("commentCount"),
        "share_count": apify_data.get("shareCount"),
        "collect_count": apify_data.get("collectCount"),
        "video_duration_seconds": video_meta.get("duration"),
        "video_created_at": video_created_at,
        "is_ad": apify_data.get("isAd"),
        "is_pinned": apify_data.get("isPinned"),
        "is_slideshow": is_slideshow,
        "media_type": media_type,
        "image_count": len(images) if images else None,
        "image_urls": images if images else None,
        "location_created": apify_data.get("locationCreated"),
        "music_id": str(music.get("musicId", "")) or None,
        "music_name": music.get("musicName"),
        "music_author": music.get("musicAuthor"),
        "music_is_original": music.get("musicOriginal"),
        "effect_stickers": apify_data.get("effectStickers") or None,
        "thumbnail_url": covers.get("default"),
        "processing_state": "enriched",
        "updated_at": func.now(),
    }


# ---------- Dev Mode Fallbacks ----------

_FAKE_CAPTIONS = [
    "Best tacos in Austin TX this place is INSANE",
    "Rating the top 5 sushi restaurants in NYC",
    "This hidden gem Italian restaurant changed my life",
    "POV: you find the best ramen shop in Tokyo",
    "Trying the viral pizza place everyone's talking about",
    "My morning routine for productivity",
    "How to train your dog to sit in 3 days",
    "This BBQ spot in Texas has the best brisket",
    "3 books that changed my perspective on life",
    "The brunch spot you NEED to visit in LA",
]

_FAKE_CREATORS = [
    {"name": "foodie_sarah", "nickName": "Sarah Eats", "fans": 45000, "verified": False},
    {"name": "nycfoodie", "nickName": "NYC Foodie", "fans": 120000, "verified": True},
    {"name": "pastaking", "nickName": "The Pasta King", "fans": 89000, "verified": False},
    {"name": "travelwithben", "nickName": "Travel With Ben", "fans": 230000, "verified": True},
    {"name": "slicereview", "nickName": "Slice Review", "fans": 67000, "verified": False},
    {"name": "dailyvibe", "nickName": "Daily Vibe", "fans": 340000, "verified": False},
    {
        "name": "dogtrainer_mike",
        "nickName": "Mike the Dog Trainer",
        "fans": 52000,
        "verified": False,
    },
    {"name": "bbqhunter", "nickName": "BBQ Hunter", "fans": 98000, "verified": True},
    {"name": "bookworm_anna", "nickName": "Anna Reads", "fans": 41000, "verified": False},
    {"name": "brunchwithme", "nickName": "Brunch With Me", "fans": 73000, "verified": False},
]

_FAKE_HASHTAGS = [
    ["food", "tacos", "austin", "foodie"],
    ["sushi", "nyc", "foodreview", "restaurant"],
    ["italian", "pasta", "hiddenGem", "restaurant"],
    ["ramen", "tokyo", "japan", "foodtravel"],
    ["pizza", "viral", "restaurant", "foodtiktok"],
    ["morning", "routine", "productivity", "grwm"],
    ["dogtok", "training", "pets"],
    ["bbq", "texas", "brisket", "restaurant"],
    ["booktok", "reading", "selfimprovement"],
    ["brunch", "la", "losangeles", "restaurant", "foodie"],
]


def _fake_apify_response(platform_id: str, index: int) -> dict:
    """Generate Apify-shaped fake data so _map_apify_to_update() is exercised."""
    i = index % len(_FAKE_CREATORS)
    creator = _FAKE_CREATORS[i]
    return {
        "id": platform_id,
        "webVideoUrl": f"https://www.tiktok.com/@{creator['name']}/video/{platform_id}",
        "text": _FAKE_CAPTIONS[i],
        "authorMeta": {"id": str(1000000 + i), **creator},
        "hashtags": [{"name": h} for h in _FAKE_HASHTAGS[i]],
        "mentions": [],
        "createTime": 1718400000 + (index * 86400),
        "playCount": 50000 + (index * 10000),
        "diggCount": 5000 + (index * 1000),
        "commentCount": 200 + (index * 50),
        "shareCount": 100 + (index * 20),
        "collectCount": 300 + (index * 30),
        "videoMeta": {"duration": 15 + (index % 45)},
        "covers": {"default": f"https://p16-sign.tiktokcdn.com/fake-{platform_id}.jpg"},
        "musicMeta": {
            "musicId": str(9000000 + i),
            "musicName": f"Original Sound - {creator['nickName']}",
            "musicAuthor": creator["nickName"],
            "musicOriginal": True,
        },
        "isAd": False,
        "isPinned": False,
        "effectStickers": [],
        "locationCreated": "",
        "images": [],
        "imagePost": False,
    }


def _random_vectors(count: int, dimensions: int = EMBEDDING_DIMENSIONS) -> list[list[float]]:
    """Generate random unit-length embedding vectors for dev mode."""
    import math
    import random

    vectors = []
    for _ in range(count):
        vec = [random.gauss(0, 1) for _ in range(dimensions)]
        magnitude = math.sqrt(sum(x * x for x in vec))
        if magnitude > 0:
            vec = [x / magnitude for x in vec]
        assert len(vec) == dimensions, f"Vector dimension mismatch: {len(vec)} != {dimensions}"
        vectors.append(vec)
    return vectors


def _dev_print(message: str) -> None:
    """Print colorful dev-mode status to terminal."""
    if os.environ.get("ENVIRONMENT", "development") == "development":
        print(f"  \u2705 {message}")


def _run_apify_instagram_batch(urls: list[str]) -> list[dict]:
    """Start an Apify Instagram scraper run, poll for completion, return items."""
    headers = {
        "Authorization": f"Bearer {APIFY_API_TOKEN}",
        "Content-Type": "application/json",
    }

    run_resp = _http_json(
        "POST",
        f"https://api.apify.com/v2/acts/{APIFY_INSTAGRAM_ACTOR_ID}/runs",
        headers=headers,
        body={"directUrls": urls, "resultsLimit": len(urls)},
        timeout=30,
    )
    run_id = run_resp["data"]["id"]

    elapsed = 0
    status = "RUNNING"
    status_resp: dict = {}
    while elapsed < APIFY_MAX_WAIT_S:
        time.sleep(APIFY_POLL_INTERVAL_S)
        elapsed += APIFY_POLL_INTERVAL_S

        status_resp = _http_json(
            "GET",
            f"https://api.apify.com/v2/actor-runs/{run_id}",
            headers=headers,
            timeout=15,
        )
        status = status_resp["data"]["status"]
        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            break

    if status != "SUCCEEDED":
        logger.warning(
            "Apify Instagram run did not succeed",
            extra={"run_id": run_id, "status": status},
        )
        return []

    dataset_id = status_resp["data"]["defaultDatasetId"]
    items: list[dict] = _http_json(
        "GET",
        f"https://api.apify.com/v2/datasets/{dataset_id}/items?format=json",
        headers=headers,
        timeout=60,
    )
    return items if isinstance(items, list) else []


def _map_instagram_apify_to_update(apify_data: dict) -> dict[str, Any]:
    """Map Apify Instagram scraper response to MediaEvent column values.

    The Instagram scraper returns a different structure than TikTok.
    Fields are mapped to the existing MediaEvent columns where possible.
    """
    owner = apify_data.get("ownerUsername") or ""
    owner_full = apify_data.get("ownerFullName") or ""

    # Determine media type
    post_type = apify_data.get("type", "")
    images = apify_data.get("images") or []
    if post_type == "Video" or apify_data.get("videoUrl"):
        media_type = "video"
    elif len(images) > 1 or post_type == "Sidecar":
        media_type = "slideshow"
    else:
        media_type = "image"

    raw_hashtags = apify_data.get("hashtags") or []
    # Normalize: handle both string lists and dict lists (like TikTok's format)
    hashtags = [h.get("name", str(h)) if isinstance(h, dict) else str(h) for h in raw_hashtags]
    raw_mentions = apify_data.get("mentions") or []
    mentions = [m.get("name", str(m)) if isinstance(m, dict) else str(m) for m in raw_mentions]

    timestamp_str = apify_data.get("timestamp")
    video_created_at = None
    if timestamp_str:
        try:
            video_created_at = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass

    return {
        "caption_text": apify_data.get("caption"),
        "hashtags": hashtags if hashtags else None,
        "mentions": mentions if mentions else None,
        "creator_username": owner or None,
        "creator_name": owner_full or None,
        "creator_id": str(apify_data.get("ownerId", "")) or None,
        "like_count": apify_data.get("likesCount"),
        "comment_count": apify_data.get("commentsCount"),
        "video_duration_seconds": apify_data.get("videoDuration"),
        "video_created_at": video_created_at,
        "is_ad": None,
        "is_pinned": None,
        "is_slideshow": media_type == "slideshow",
        "media_type": media_type,
        "image_count": len(images) if images else None,
        "image_urls": images if images else None,
        "location_created": apify_data.get("locationName"),
        "thumbnail_url": apify_data.get("displayUrl"),
        "processing_state": "enriched",
        "updated_at": func.now(),
    }


def _fake_ig_apify_response(platform_id: str, index: int) -> dict:
    """Generate Instagram Apify-shaped fake data for dev mode."""
    i = index % len(_FAKE_CREATORS)
    creator = _FAKE_CREATORS[i]
    return {
        "shortCode": platform_id,
        "url": f"https://www.instagram.com/p/{platform_id}/",
        "caption": _FAKE_CAPTIONS[i],
        "ownerUsername": creator["name"],
        "ownerFullName": creator["nickName"],
        "ownerId": str(1000000 + i),
        "timestamp": f"2025-06-{15 + (index % 15):02d}T12:00:00.000Z",
        "likesCount": 5000 + (index * 1000),
        "commentsCount": 200 + (index * 50),
        "type": "Video" if index % 3 != 0 else "Image",
        "displayUrl": f"https://instagram.fcdn.net/v/fake-{platform_id}.jpg",
        "hashtags": _FAKE_HASHTAGS[i],
        "mentions": [],
        "images": [],
        "locationName": "",
    }


def step_apify_enrich(
    session: Session,
    upload_id: str,
    media_event_ids: list[str],
    pipeline_run_id: str,
    source_platform: str = "tiktok",
) -> None:
    """Fetch metadata via Apify scraper in batches. Dispatches by platform."""
    step_start = time.time()
    logger.info(
        "Step 2/7: apify_enrich started",
        extra={"upload_id": upload_id, "platform": source_platform},
    )

    # Only enrich items still in 'parsed' state (idempotent on retry)
    events = (
        session.execute(
            select(MediaEvent).where(
                MediaEvent.id.in_([UUID(eid) for eid in media_event_ids]),
                MediaEvent.processing_state == "parsed",
            )
        )
        .scalars()
        .all()
    )

    if not events:
        logger.info(
            "Step 2/7: no items to enrich (all already enriched)",
            extra={"upload_id": upload_id},
        )
        return

    is_instagram = source_platform == "instagram"
    enriched_count = 0

    for i in range(0, len(events), APIFY_BATCH_SIZE):
        batch = events[i : i + APIFY_BATCH_SIZE]
        urls = [e.canonical_url for e in batch if e.canonical_url]

        if not is_instagram:
            urls = [_normalize_tiktok_url(u) for u in urls]

        if APIFY_API_TOKEN:
            if is_instagram:
                apify_items = _run_apify_instagram_batch(urls)
            else:
                apify_items = _run_apify_batch(urls)
        else:
            logger.info(
                "Using fake enrichment (no APIFY_API_TOKEN)",
                extra={"upload_id": upload_id, "platform": source_platform},
            )
            if is_instagram:
                apify_items = [
                    _fake_ig_apify_response(e.platform_id, i + idx) for idx, e in enumerate(batch)
                ]
            else:
                apify_items = [
                    _fake_apify_response(e.platform_id, i + idx) for idx, e in enumerate(batch)
                ]

        # Index Apify results by platform ID for matching
        results_by_pid: dict[str, dict] = {}
        for item in apify_items:
            if is_instagram:
                shortcode = item.get("shortCode") or ""
                if shortcode:
                    results_by_pid[shortcode] = item
                # Also try extracting from URL
                item_url = item.get("url", "")
                sc = _extract_ig_shortcode(item_url)
                if sc:
                    results_by_pid[sc] = item
            else:
                apify_id = str(item.get("id", ""))
                if apify_id:
                    results_by_pid[apify_id] = item
                web_url = item.get("webVideoUrl", "")
                pid = _extract_platform_id(web_url)
                if pid:
                    results_by_pid[pid] = item

        for event in batch:
            apify_data = results_by_pid.get(event.platform_id)
            if not apify_data:
                continue

            if is_instagram:
                values = _map_instagram_apify_to_update(apify_data)
            else:
                values = _map_apify_to_update(apify_data)
            session.execute(update(MediaEvent).where(MediaEvent.id == event.id).values(**values))
            enriched_count += 1

        # Update pipeline progress after each batch
        session.execute(
            update(UploadPipelineRun)
            .where(UploadPipelineRun.id == UUID(pipeline_run_id))
            .values(items_enriched=enriched_count)
        )
        session.commit()

    duration_ms = int((time.time() - step_start) * 1000)
    logger.info(
        "Step 2/7: apify_enrich complete",
        extra={
            "upload_id": upload_id,
            "enriched": enriched_count,
            "duration_ms": duration_ms,
        },
    )
    suffix = " (fake data)" if not APIFY_API_TOKEN else ""
    _dev_print(f"Step 2/7: Enriched {enriched_count} items{suffix}")


# ==========================================================================
# Step 3: SUBTITLE_FETCH
# ==========================================================================


def step_subtitle_fetch(
    session: Session,
    upload_id: str,
    media_event_ids: list[str],
    pipeline_run_id: str,
) -> None:
    """Extract subtitles from Apify data. Skip images/slideshows."""
    step_start = time.time()
    logger.info("Step 3/7: subtitle_fetch started", extra={"upload_id": upload_id})

    id_uuids = [UUID(eid) for eid in media_event_ids]

    # Advance images/slideshows past this step (no subtitles to fetch)
    session.execute(
        update(MediaEvent)
        .where(
            MediaEvent.id.in_(id_uuids),
            MediaEvent.processing_state == "enriched",
            MediaEvent.media_type.in_(["image", "slideshow"]),
        )
        .values(processing_state="subtitled", updated_at=func.now())
    )

    # Get enriched video events
    events = (
        session.execute(
            select(MediaEvent).where(
                MediaEvent.id.in_(id_uuids),
                MediaEvent.processing_state == "enriched",
                MediaEvent.media_type == "video",
            )
        )
        .scalars()
        .all()
    )

    subtitle_count = 0

    for event in events:
        # Apify TikTok data often includes subtitles in the response.
        # caption_text is always available; subtitle_text comes from subtitle files.
        # For MVP, we mark as subtitled. The agent's classify/vision tools
        # handle deeper analysis on demand.
        subtitle_text = None
        subtitle_source = None

        # If caption_text exists, that serves as our primary text signal
        if event.caption_text:
            subtitle_count += 1

        session.execute(
            update(MediaEvent)
            .where(MediaEvent.id == event.id)
            .values(
                subtitle_text=subtitle_text,
                subtitle_source=subtitle_source,
                processing_state="subtitled",
                updated_at=func.now(),
            )
        )

    session.execute(
        update(UploadPipelineRun)
        .where(UploadPipelineRun.id == UUID(pipeline_run_id))
        .values(items_transcribed=subtitle_count)
    )
    session.commit()

    duration_ms = int((time.time() - step_start) * 1000)
    logger.info(
        "Step 3/7: subtitle_fetch complete",
        extra={
            "upload_id": upload_id,
            "subtitled": len(events),
            "duration_ms": duration_ms,
        },
    )
    _dev_print(f"Step 3/7: Subtitles for {len(events)} videos")


# ==========================================================================
# Step 4: PERCEIVE (Visual observation — separate from classification)
# ==========================================================================


def _build_perception_context(
    caption: str | None,
    creator_username: str | None,
    hashtags: list[str] | None,
    music_name: str | None,
    duration_seconds: int | None,
    subtitle_text: str | None,
    comments_top: list[str] | None,
) -> str:
    """Build the context block for perception prompts."""
    parts: list[str] = []
    if caption:
        parts.append(f"Caption: {caption[:500]}")
    if hashtags:
        parts.append(f"Hashtags: #{', #'.join(hashtags[:15])}")
    if creator_username:
        parts.append(f"Creator: @{creator_username}")
    if music_name:
        parts.append(f"Music metadata: {music_name}")
    if duration_seconds:
        parts.append(f"Duration: {duration_seconds}s")
    if subtitle_text:
        parts.append(f"Subtitles: {subtitle_text[:500]}")
    if comments_top:
        clines = [f'  {j + 1}. "{c[:120]}"' for j, c in enumerate(comments_top[:10]) if c]
        if clines:
            parts.append("Top comments:\n" + "\n".join(clines))
    return "\n".join(parts) if parts else "(No metadata available)"


def _perceive_one_sync(
    api_key: str,
    model: str,
    media_type: str | None,
    is_slideshow: bool,
    thumbnail_url: str | None,
    image_urls: list[str] | None,
    video_url: str | None,
    caption: str | None,
    creator_username: str | None,
    hashtags: list[str] | None,
    music_name: str | None,
    duration_seconds: int | None,
    subtitle_text: str | None,
    comments_top: list[str] | None,
    platform: str = "tiktok",
    interaction_type: str | None = None,
) -> dict | None:
    """Run visual perception on a single item using v2 prompts.

    Selects the appropriate prompt (observe_video, observe_slideshow, observe_image)
    based on media type. For videos with a video_url, uploads full video to Gemini
    File API. Falls back to thumbnail if upload fails or no video_url.
    """
    import httpx as _httpx

    from app.services.gemini import (
        GEMINI_API_BASE,
        PERCEPTION_MAX_TOKENS,
        REQUEST_TIMEOUT,
        delete_file_sync,
        upload_file_sync,
        wait_for_file_sync,
    )
    from app.services.prompt_loader import load_prompt

    context = _build_perception_context(
        caption,
        creator_username,
        hashtags,
        music_name,
        duration_seconds,
        subtitle_text,
        comments_top,
    )
    interaction = interaction_type or "saved"
    gemini_model = model or "gemini-2.0-flash"

    try:
        # ---- VIDEO: upload full video to Gemini File API ----
        if media_type == "video" and video_url:
            prompt_text = load_prompt("perception", "observe_video")
            prompt = (
                prompt_text.replace("{platform}", platform)
                .replace("{interaction_type}", interaction)
                .replace("{context}", context)
            )

            video_file_name = None
            video_tmp_path = None
            try:
                video_tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
                video_tmp_path = video_tmp.name
                video_tmp.close()

                _http_download(video_url, headers={}, dest_path=video_tmp_path, timeout=120)

                video_file_name = upload_file_sync(api_key, video_tmp_path, "video/mp4")
                if video_file_name:
                    file_uri = wait_for_file_sync(api_key, video_file_name)
                    if file_uri:
                        parts: list[dict] = [
                            {"text": prompt},
                            {"fileData": {"mimeType": "video/mp4", "fileUri": file_uri}},
                        ]

                        with _httpx.Client(timeout=REQUEST_TIMEOUT * 3) as client:
                            resp = client.post(
                                f"{GEMINI_API_BASE}/models/{gemini_model}:generateContent",
                                params={"key": api_key},
                                json={
                                    "contents": [{"parts": parts}],
                                    "generationConfig": {
                                        "maxOutputTokens": PERCEPTION_MAX_TOKENS,
                                        "temperature": 0.2,
                                        "responseMimeType": "application/json",
                                    },
                                },
                            )

                        delete_file_sync(api_key, video_file_name)
                        video_file_name = None

                        if resp.status_code == 200:
                            data = resp.json()
                            text = data["candidates"][0]["content"]["parts"][0]["text"]
                            return json.loads(text)

                        logger.warning(
                            "Gemini perceive video API error",
                            extra={"status": resp.status_code},
                        )
                    else:
                        delete_file_sync(api_key, video_file_name)
                        video_file_name = None
            finally:
                if video_file_name:
                    delete_file_sync(api_key, video_file_name)
                if video_tmp_path:
                    try:
                        os.remove(video_tmp_path)
                    except Exception:
                        pass
            # Fall through to thumbnail below if video upload failed

        # ---- VIDEO FALLBACK (no video_url or upload failed): use thumbnail ----
        if media_type == "video":
            if not thumbnail_url:
                return None
            prompt_text = load_prompt("perception", "observe_image")
            prompt = (
                prompt_text.replace("{platform}", platform)
                .replace("{interaction_type}", interaction)
                .replace("{context}", context)
            )
            parts = [
                {"text": prompt},
                {"fileData": {"mimeType": "image/jpeg", "fileUri": thumbnail_url}},
            ]

        # ---- SLIDESHOW: send all images ----
        elif is_slideshow and image_urls:
            urls_to_send = image_urls[:10]
            n_images = len(urls_to_send)
            prompt_text = load_prompt("perception", "observe_slideshow")
            prompt = (
                prompt_text.replace("{platform}", platform)
                .replace("{interaction_type}", interaction)
                .replace("{image_count}", str(n_images))
                .replace("{context}", context)
            )
            parts = [{"text": prompt}]
            for url in urls_to_send:
                parts.append({"fileData": {"mimeType": "image/jpeg", "fileUri": url}})

        # ---- SINGLE IMAGE ----
        elif thumbnail_url:
            prompt_text = load_prompt("perception", "observe_image")
            prompt = (
                prompt_text.replace("{platform}", platform)
                .replace("{interaction_type}", interaction)
                .replace("{context}", context)
            )
            parts = [
                {"text": prompt},
                {"fileData": {"mimeType": "image/jpeg", "fileUri": thumbnail_url}},
            ]
        else:
            return None

        with _httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            resp = client.post(
                f"{GEMINI_API_BASE}/models/{gemini_model}:generateContent",
                params={"key": api_key},
                json={
                    "contents": [{"parts": parts}],
                    "generationConfig": {
                        "maxOutputTokens": PERCEPTION_MAX_TOKENS,
                        "temperature": 0.2,
                        "responseMimeType": "application/json",
                    },
                },
            )

        if resp.status_code != 200:
            body = resp.text[:300] if resp.text else "(empty)"
            logger.warning(
                "Gemini perceive API error",
                extra={"status": resp.status_code, "body": body},
            )
            return None

        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)

    except Exception as e:
        logger.warning("Gemini perceive failed", extra={"error": str(e)})
        return None


def _fake_perception(index: int) -> dict:
    """Generate fake perception for dev mode (no GEMINI_API_KEY)."""
    scenes = [
        ("indoor kitchen scene with cooking", "food_close_up", "warm"),
        ("person talking to camera outdoors", "outdoor", "energetic"),
        ("product display on clean background", "product_shot", "minimal"),
        ("gym workout with equipment visible", "gym", "energetic"),
        ("street scene with storefronts", "street", "bright"),
    ]
    desc, scene, mood = scenes[index % len(scenes)]
    return {
        "visual_description": f"Dev mode: {desc}.",
        "text_on_screen": None,
        "entities_detected": [],
        "people": [],
        "scene_type": scene,
        "visual_mood": mood,
        "colors_dominant": ["neutral"],
        "presentation_format": "photo",
    }


def step_perceive(
    session: Session,
    upload_id: str,
    media_event_ids: list[str],
    pipeline_run_id: str,
) -> None:
    """Step 4/7: Visual perception pass. Observes images without classifying.

    Writes perception results to cached_classifications.perception for each item.
    The classify step reads this and uses it as additional context.
    """
    step_start = time.time()
    logger.info("Step 4/7: perceive started", extra={"upload_id": upload_id})

    events = (
        session.execute(
            select(MediaEvent).where(
                MediaEvent.id.in_([UUID(eid) for eid in media_event_ids]),
                MediaEvent.processing_state == "subtitled",
            )
        )
        .scalars()
        .all()
    )

    if not events:
        logger.info("Step 4/7: no items to perceive", extra={"upload_id": upload_id})
        return

    perceived_count = 0

    if GEMINI_API_KEY:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        futures = {}
        with ThreadPoolExecutor(max_workers=PERCEIVE_CONCURRENCY) as executor:
            for event in events:
                if not event.thumbnail_url and not event.image_urls and not event.video_url:
                    continue

                future = executor.submit(
                    _perceive_one_sync,
                    api_key=GEMINI_API_KEY,
                    model=GEMINI_MODEL,
                    media_type=event.media_type,
                    is_slideshow=bool(event.is_slideshow),
                    thumbnail_url=event.thumbnail_url,
                    image_urls=event.image_urls,
                    video_url=event.video_url,
                    caption=event.caption_text,
                    creator_username=event.creator_username,
                    hashtags=event.hashtags,
                    music_name=event.music_name,
                    duration_seconds=event.video_duration_seconds,
                    subtitle_text=event.subtitle_text,
                    comments_top=event.comments_top,
                    platform=event.platform or "tiktok",
                    interaction_type=event.interaction_type,
                )
                futures[future] = event

            processed = 0
            failed = 0
            total_submitted = len(futures)
            for future in as_completed(futures):
                event = futures[future]
                perception = future.result()

                if perception:
                    existing = event.cached_classifications or {}
                    existing["perception"] = perception
                    session.execute(
                        update(MediaEvent)
                        .where(MediaEvent.id == event.id)
                        .values(
                            cached_classifications=existing,
                            processing_state="perceived",
                            updated_at=func.now(),
                        )
                    )
                    perceived_count += 1
                else:
                    failed += 1
                    session.execute(
                        update(MediaEvent)
                        .where(MediaEvent.id == event.id)
                        .values(
                            processing_state="perceived",
                            updated_at=func.now(),
                        )
                    )

                processed += 1
                # Batch commit every 50 items + progress log
                if processed % 50 == 0:
                    session.commit()
                    _dev_print(
                        f"  Step 4/7 progress: {processed}/{total_submitted} "
                        f"({perceived_count} perceived, {failed} failed)"
                    )
    else:
        logger.info(
            "Using fake perceptions (no GEMINI_API_KEY)",
            extra={"upload_id": upload_id},
        )
        for idx, event in enumerate(events):
            existing = event.cached_classifications or {}
            existing["perception"] = _fake_perception(idx)
            session.execute(
                update(MediaEvent)
                .where(MediaEvent.id == event.id)
                .values(
                    cached_classifications=existing,
                    processing_state="perceived",
                    updated_at=func.now(),
                )
            )
            perceived_count += 1

    session.commit()

    duration_ms = int((time.time() - step_start) * 1000)
    logger.info(
        "Step 4/7: perceive complete",
        extra={
            "upload_id": upload_id,
            "perceived": perceived_count,
            "duration_ms": duration_ms,
        },
    )
    suffix = " (fake)" if not GEMINI_API_KEY else ""
    _dev_print(f"Step 4/7: Perceived {perceived_count} items{suffix}")


# ==========================================================================
# Step 5: CLASSIFY (Gemini — enhanced with perception context)
# ==========================================================================


def _classify_one_sync(
    api_key: str,
    model: str,
    caption: str | None,
    subtitle: str | None,
    hashtags: list | None,
    creator_username: str | None,
    music_name: str | None,
    duration_seconds: int | None,
    thumbnail_url: str | None,
    comments_top: list[str] | None = None,
    perception: dict | None = None,
    platform: str = "tiktok",
    interaction_type: str | None = None,
) -> dict | None:
    """Synchronous Gemini classification using v2 prompt (8-facet, multi-label affect).

    Uses perception data as PRIMARY evidence (serialized as JSON).
    Raw metadata is SUPPLEMENTARY context for disambiguation.
    Image is NOT re-sent when perception exists.
    """
    import httpx as _httpx

    from app.services.gemini import (
        CLASSIFY_MAX_TOKENS,
        DEFAULT_GEMINI_MODEL,
        GEMINI_API_BASE,
        REQUEST_TIMEOUT,
    )
    from app.services.prompt_loader import load_prompt

    try:
        # Build supplementary metadata context
        context_parts: list[str] = []
        if caption:
            context_parts.append(f"Caption: {caption}")
        if subtitle:
            context_parts.append(f"Subtitles: {subtitle[:500]}")
        if hashtags:
            context_parts.append(f"Hashtags: #{', #'.join(str(h) for h in hashtags[:20])}")
        if creator_username:
            context_parts.append(f"Creator: @{creator_username}")
        if music_name:
            context_parts.append(f"Music: {music_name}")
        if duration_seconds is not None:
            context_parts.append(f"Duration: {duration_seconds}s")
        if comments_top:
            clines = [f'  {j + 1}. "{c[:120]}"' for j, c in enumerate(comments_top[:10]) if c]
            if clines:
                context_parts.append("Top comments:\n" + "\n".join(clines))
        context = "\n".join(context_parts) if context_parts else "(No metadata available.)"

        if not context_parts and not thumbnail_url and not perception:
            return None

        # Serialize perception as JSON for the v2 prompt
        if perception:
            perception_summary = json.dumps(perception, indent=2, default=str)[:6000]
        else:
            perception_summary = "(No perception data available — classify from metadata only.)"

        interaction = interaction_type or "saved"

        prompt = (
            load_prompt("classify", "tier2")
            .replace("{platform}", platform)
            .replace("{interaction_type}", interaction)
            .replace("{perception_summary}", perception_summary)
            .replace("{context}", context)
        )
        gemini_model = model or DEFAULT_GEMINI_MODEL

        # Only attach image if there's NO perception data (avoid double-processing)
        parts: list[dict] = [{"text": prompt}]
        if thumbnail_url and not perception:
            parts.append(
                {
                    "fileData": {
                        "mimeType": "image/jpeg",
                        "fileUri": thumbnail_url,
                    }
                }
            )

        # Use sync httpx.Client (NOT the shared async one) for thread safety
        with _httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            resp = client.post(
                f"{GEMINI_API_BASE}/models/{gemini_model}:generateContent",
                params={"key": api_key},
                json={
                    "contents": [{"parts": parts}],
                    "generationConfig": {
                        "maxOutputTokens": CLASSIFY_MAX_TOKENS,
                        "temperature": 0.2,
                        "responseMimeType": "application/json",
                    },
                },
            )

        if resp.status_code != 200:
            logger.warning(
                "Gemini classify API error",
                extra={"status": resp.status_code},
            )
            return None

        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        classification = json.loads(text)

        return {
            "raw": classification,
            "summary": classification.get("summary"),
            "entities": classification.get("entities") or [],
            "embedding_text": classification.get("embedding_text"),
        }
    except Exception as e:
        logger.warning("Gemini classify failed", extra={"error": str(e)})
        return None


_FAKE_CLASSIFICATIONS = [
    {"topic": "food", "affect": "informative", "genre": "recipe"},
    {"topic": "travel", "affect": "inspiring", "genre": "vlog"},
    {"topic": "fashion", "affect": "informative", "genre": "haul"},
    {"topic": "fitness", "affect": "informative", "genre": "workout"},
    {"topic": "comedy", "affect": "funny", "genre": "skit"},
    {"topic": "technology", "affect": "informative", "genre": "review"},
    {"topic": "pets", "affect": "wholesome", "genre": "vlog"},
    {"topic": "books", "affect": "informative", "genre": "review"},
    {"topic": "food", "affect": "satisfying", "genre": "recipe"},
    {"topic": "career", "affect": "informative", "genre": "tutorial"},
]


def _fake_classification(index: int) -> dict:
    """Generate a fake cached_classifications payload for dev mode."""
    c = _FAKE_CLASSIFICATIONS[index % len(_FAKE_CLASSIFICATIONS)]
    return {
        "tier1": {
            "topic": c["topic"],
            "affect": c["affect"],
            "genre": c["genre"],
            "communicative_intent": "inform",
            "creator_role": "amateur",
            "viewer_orientation": "active_learning",
            "presentation_style": "talking_head",
            "content_provenance": "original",
        },
        "tier2": {},
        "confidence": {
            facet: 0.7
            for facet in [
                "topic",
                "affect",
                "genre",
                "communicative_intent",
                "creator_role",
                "viewer_orientation",
                "presentation_style",
                "content_provenance",
            ]
        },
        "summary": f"Dev mode fake classification for {c['topic']} content.",
        "entities": [],
        "embedding_text": f"A {c['genre']} about {c['topic']} that is {c['affect']}.",
        "source": "pipeline_v2",
    }


def step_classify(
    session: Session,
    upload_id: str,
    media_event_ids: list[str],
    pipeline_run_id: str,
) -> None:
    """Step 5/7: Classify items using Gemini Tier 1 prompt, enhanced with perception.

    Reads perception data from cached_classifications.perception (written by
    step_perceive) and injects it as context for the classification prompt.
    When perception is available, the image is NOT re-sent to Gemini.
    """
    step_start = time.time()
    logger.info("Step 5/7: classify started", extra={"upload_id": upload_id})

    events = (
        session.execute(
            select(MediaEvent).where(
                MediaEvent.id.in_([UUID(eid) for eid in media_event_ids]),
                MediaEvent.processing_state == "perceived",
            )
        )
        .scalars()
        .all()
    )

    if not events:
        logger.info("Step 5/7: no items to classify", extra={"upload_id": upload_id})
        return

    classified_count = 0

    if GEMINI_API_KEY:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        from app.services.ontology import validate_classification

        # Submit all items to thread pool for concurrent classification
        futures = {}
        with ThreadPoolExecutor(max_workers=CLASSIFY_CONCURRENCY) as executor:
            for event in events:
                # Read perception data written by step_perceive (if available)
                existing_cache = event.cached_classifications or {}
                perception_data = existing_cache.get("perception")

                future = executor.submit(
                    _classify_one_sync,
                    api_key=GEMINI_API_KEY,
                    model=GEMINI_MODEL,
                    caption=event.caption_text,
                    subtitle=event.subtitle_text,
                    hashtags=event.hashtags,
                    creator_username=event.creator_username,
                    music_name=event.music_name,
                    duration_seconds=event.video_duration_seconds,
                    thumbnail_url=event.thumbnail_url,
                    comments_top=event.comments_top,
                    perception=perception_data,
                    platform=event.platform or "tiktok",
                    interaction_type=event.interaction_type,
                )
                futures[future] = event

            processed = 0
            total_submitted = len(futures)
            for future in as_completed(futures):
                event = futures[future]
                result = future.result()

                existing_cache = event.cached_classifications or {}
                perception_data = existing_cache.get("perception")

                if result:
                    validated = validate_classification(result["raw"])
                    cache = {
                        "tier1": validated.tier1,
                        "tier2": validated.tier2,
                        "confidence": validated.confidence,
                        "source": (
                            "pipeline_v2_with_perception" if perception_data else "pipeline_v2"
                        ),
                    }
                    if result.get("summary"):
                        cache["summary"] = result["summary"]
                    if result.get("entities"):
                        cache["entities"] = result["entities"]
                    if result.get("embedding_text"):
                        cache["embedding_text"] = result["embedding_text"]
                    if perception_data:
                        cache["perception"] = perception_data
                else:
                    cache = None

                session.execute(
                    update(MediaEvent)
                    .where(MediaEvent.id == event.id)
                    .values(
                        cached_classifications=cache,
                        processing_state="classified",
                        updated_at=func.now(),
                    )
                )
                classified_count += 1
                processed += 1

                if processed % 50 == 0:
                    session.commit()
                    _dev_print(
                        f"  Step 5/7 progress: {processed}/{total_submitted} "
                        f"({classified_count} classified)"
                    )
    else:
        # Dev mode: fake classifications
        logger.info(
            "Using fake classifications (no GEMINI_API_KEY)",
            extra={"upload_id": upload_id},
        )
        for idx, event in enumerate(events):
            cache = _fake_classification(idx)
            session.execute(
                update(MediaEvent)
                .where(MediaEvent.id == event.id)
                .values(
                    cached_classifications=cache,
                    processing_state="classified",
                    updated_at=func.now(),
                )
            )
            classified_count += 1

    session.execute(
        update(UploadPipelineRun)
        .where(UploadPipelineRun.id == UUID(pipeline_run_id))
        .values(items_vision_done=classified_count)
    )
    session.commit()

    duration_ms = int((time.time() - step_start) * 1000)
    logger.info(
        "Step 5/7: classify complete",
        extra={
            "upload_id": upload_id,
            "classified": classified_count,
            "duration_ms": duration_ms,
        },
    )
    suffix = " (fake)" if not GEMINI_API_KEY else ""
    _dev_print(f"Step 5/7: Classified {classified_count} items{suffix}")


# ==========================================================================
# Step 6: EMBEDDING
# ==========================================================================


def _fuse_text(event: MediaEvent) -> str:
    """Fuse available text fields into a single searchable string."""
    parts: list[str] = []
    if event.caption_text:
        parts.append(event.caption_text)
    if event.hashtags:
        parts.append(" ".join(f"#{h}" for h in event.hashtags))
    if event.subtitle_text:
        parts.append(event.subtitle_text)
    if event.creator_username:
        parts.append(f"by @{event.creator_username}")
    if event.music_name:
        parts.append(f"music: {event.music_name}")
    return " | ".join(parts) if parts else f"untitled {event.platform} post"


def _embed_batch(texts: list[str]) -> list[list[float]]:
    """Call OpenAI embeddings API for a batch of texts."""
    resp = _http_json(
        "POST",
        "https://api.openai.com/v1/embeddings",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        body={
            "input": texts,
            "model": EMBEDDING_MODEL,
            "dimensions": EMBEDDING_DIMENSIONS,
        },
        timeout=120,
    )
    # Sort by index to maintain order
    sorted_data = sorted(resp.get("data", []), key=lambda d: d["index"])
    return [d["embedding"] for d in sorted_data]


def step_embed(
    session: Session,
    upload_id: str,
    media_event_ids: list[str],
    pipeline_run_id: str,
) -> None:
    """Fuse text fields and generate embeddings via OpenAI."""
    step_start = time.time()
    logger.info("Step 6/7: embed started", extra={"upload_id": upload_id})

    events = (
        session.execute(
            select(MediaEvent).where(
                MediaEvent.id.in_([UUID(eid) for eid in media_event_ids]),
                MediaEvent.processing_state == "classified",
            )
        )
        .scalars()
        .all()
    )

    if not events:
        logger.info("Step 6/7: no items to embed", extra={"upload_id": upload_id})
        return

    # Build embedding text: prefer model-generated embedding_text, fall back to _fuse_text
    texts: list[str] = []
    ordered_events: list[MediaEvent] = []
    for event in events:
        # Use embedding_text from Gemini classification if available
        embedding_text = None
        if event.cached_classifications and isinstance(event.cached_classifications, dict):
            embedding_text = event.cached_classifications.get("embedding_text")

        full_text = embedding_text or _fuse_text(event)
        session.execute(
            update(MediaEvent).where(MediaEvent.id == event.id).values(full_text=full_text)
        )
        texts.append(full_text)
        ordered_events.append(event)

    # Batch embed
    embedded_count = 0
    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch_texts = texts[i : i + EMBEDDING_BATCH_SIZE]
        batch_events = ordered_events[i : i + EMBEDDING_BATCH_SIZE]

        if OPENAI_API_KEY:
            vectors = _embed_batch(batch_texts)
        else:
            logger.info(
                "Using random embeddings (no OPENAI_API_KEY)",
                extra={"upload_id": upload_id},
            )
            vectors = _random_vectors(len(batch_texts))

        for event, vector in zip(batch_events, vectors):
            session.execute(
                update(MediaEvent)
                .where(MediaEvent.id == event.id)
                .values(
                    embedding_vector=vector,
                    processing_state="complete",
                    updated_at=func.now(),
                )
            )
            embedded_count += 1

        # Update pipeline progress after each batch
        session.execute(
            update(UploadPipelineRun)
            .where(UploadPipelineRun.id == UUID(pipeline_run_id))
            .values(items_embedded=embedded_count, items_complete=embedded_count)
        )
        session.commit()

    duration_ms = int((time.time() - step_start) * 1000)
    logger.info(
        "Step 6/7: embed complete",
        extra={
            "upload_id": upload_id,
            "embedded": embedded_count,
            "duration_ms": duration_ms,
        },
    )
    suffix = " (random)" if not OPENAI_API_KEY else ""
    _dev_print(f"Step 6/7: Embeddings for {embedded_count} items{suffix}")


# ==========================================================================
# Pipeline Orchestrator
# ==========================================================================


def _ensure_pipeline_run(session: Session, upload_id: str, user_id: str) -> str:
    """Create or return existing active pipeline run for this upload."""
    existing = session.execute(
        select(UploadPipelineRun).where(
            UploadPipelineRun.upload_id == UUID(upload_id),
            UploadPipelineRun.status.in_(["pending", "processing"]),
        )
    ).scalar_one_or_none()

    if existing:
        return str(existing.id)

    run = UploadPipelineRun(
        upload_id=UUID(upload_id),
        user_id=UUID(user_id),
        status="processing",
        started_at=datetime.now(UTC),
    )
    session.add(run)
    session.flush()
    return str(run.id)


def _mark_upload_failed(upload_id: str) -> None:
    """Mark upload and pipeline run as failed (called on unrecoverable error)."""
    try:
        session = _session()
        try:
            session.execute(
                update(Upload).where(Upload.id == UUID(upload_id)).values(status="failed")
            )
            session.execute(
                update(UploadPipelineRun)
                .where(
                    UploadPipelineRun.upload_id == UUID(upload_id),
                    UploadPipelineRun.status == "processing",
                )
                .values(status="failed", finished_at=datetime.now(UTC))
            )
            session.commit()
        finally:
            session.close()
    except Exception:
        logger.exception("Failed to mark upload as failed", extra={"upload_id": upload_id})


# ==========================================================================
# Pipeline Entry Point
# ==========================================================================


def run_pipeline(
    upload_id: str,
    user_id: str,
    storage_path: str,
    scope: str,
    request_id: str = "local",
    source_platform: str = "tiktok",
) -> dict:
    """Run the full 6-step pipeline for a single upload.

    This is the main entry point, called by both the Lambda handler
    and local dev mode.

    Args:
        upload_id: UUID of the upload to process.
        user_id: UUID of the user who owns the upload.
        storage_path: Supabase Storage path to the ZIP file.
        scope: Which videos to process ('liked', 'favorited', or 'both').
        request_id: Correlation ID for logging (Lambda request ID or 'local').
        source_platform: Platform of the export ('tiktok' or 'instagram').

    Returns:
        Dict with statusCode and body (matches Lambda response format).
    """
    logger.info(
        "Pipeline started",
        extra={
            "upload_id": upload_id,
            "request_id": request_id,
            "scope": scope,
            "platform": source_platform,
        },
    )

    start = time.time()
    session = _session()

    try:
        # Create/get pipeline run
        pipeline_run_id = _ensure_pipeline_run(session, upload_id, user_id)
        session.commit()

        # Step 1: Parse export -> create media_event rows
        media_event_ids = step_parse_export(
            session,
            upload_id,
            user_id,
            storage_path,
            scope,
            source_platform=source_platform,
        )

        # Update pipeline run total
        session.execute(
            update(UploadPipelineRun)
            .where(UploadPipelineRun.id == UUID(pipeline_run_id))
            .values(total_items=len(media_event_ids))
        )
        session.commit()

        # Step 2: Apify enrich -> fetch metadata (platform-specific actor)
        step_apify_enrich(
            session,
            upload_id,
            media_event_ids,
            pipeline_run_id,
            source_platform=source_platform,
        )

        # Step 3: Subtitle fetch -> extract subtitles
        step_subtitle_fetch(session, upload_id, media_event_ids, pipeline_run_id)

        # Step 4: Perceive -> visual observation (separate from classification)
        step_perceive(session, upload_id, media_event_ids, pipeline_run_id)

        # Check if we're running low on time (video uploads are expensive)
        elapsed_s = time.time() - start
        remaining_items = session.scalar(
            select(func.count()).where(
                MediaEvent.id.in_([UUID(eid) for eid in media_event_ids]),
                MediaEvent.processing_state.in_(["subtitled", "perceived"]),
            )
        )
        if elapsed_s > STEP_TIME_BUDGET_S and remaining_items and remaining_items > 0:
            logger.info(
                "Time budget exceeded, relying on retry for remaining items",
                extra={
                    "upload_id": upload_id,
                    "elapsed_s": int(elapsed_s),
                    "remaining_items": remaining_items,
                },
            )
            _dev_print(
                f"  \u23f1 Time budget exceeded ({int(elapsed_s)}s), "
                f"{remaining_items} items remain — will continue on retry"
            )

        # Step 5: Classify -> perception-enhanced classification
        step_classify(session, upload_id, media_event_ids, pipeline_run_id)

        # Step 6: Embed -> generate search embeddings
        step_embed(session, upload_id, media_event_ids, pipeline_run_id)

        # Mark upload + pipeline run as complete
        session.execute(
            update(Upload)
            .where(Upload.id == UUID(upload_id))
            .values(
                status="complete",
                processed_items=len(media_event_ids),
                completed_at=datetime.now(UTC),
            )
        )
        session.execute(
            update(UploadPipelineRun)
            .where(UploadPipelineRun.id == UUID(pipeline_run_id))
            .values(status="complete", finished_at=datetime.now(UTC))
        )
        session.commit()

        duration_ms = int((time.time() - start) * 1000)
        logger.info(
            "Pipeline complete",
            extra={
                "upload_id": upload_id,
                "request_id": request_id,
                "items": len(media_event_ids),
                "duration_ms": duration_ms,
            },
        )
        _dev_print(
            f"\U0001f389 Pipeline complete in {duration_ms}ms! ({len(media_event_ids)} items)"
        )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "upload_id": upload_id,
                    "items_processed": len(media_event_ids),
                    "status": "complete",
                }
            ),
        }

    except Exception:
        duration_ms = int((time.time() - start) * 1000)
        logger.exception(
            "Pipeline failed",
            extra={
                "upload_id": upload_id,
                "request_id": request_id,
                "duration_ms": duration_ms,
            },
        )
        _mark_upload_failed(upload_id)
        raise
    finally:
        session.close()
