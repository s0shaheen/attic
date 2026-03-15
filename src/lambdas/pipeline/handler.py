"""Unified 4-step pipeline handler for TikTok data export processing.

SQS -> single Lambda: parse_export -> apify_enrich -> subtitle_fetch -> embed

Each step is idempotent (upserts with deterministic IDs).
Single invocation processes one upload (SQS BatchSize: 1).
Steps advance items through processing_state: parsed -> enriched -> subtitled -> complete.
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import create_engine, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, sessionmaker

from common.idempotency import generate_idempotency_key
from common.logger import get_logger

# Imports from CommonLayer (bundled backend app/)
from app.models.media_event import MediaEvent
from app.models.upload import Upload
from app.models.upload_pipeline_run import UploadPipelineRun

# Prevent app.services.__init__ from loading (it eagerly imports uploads.py →
# config.py which requires all backend env vars). We only need tiktok_parser.
import sys
import types

_svc_stub = types.ModuleType("app.services")
_svc_stub.__path__ = []  # Makes it a package so submodule imports work
_svc_stub.__package__ = "app.services"
sys.modules.setdefault("app.services", _svc_stub)

from app.services.tiktok_parser import parse_tiktok_export  # noqa: E402

logger = get_logger("pipeline")

# ---------- Configuration ----------

DATABASE_URL = os.environ.get("DATABASE_URL", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SECRET_KEY = os.environ.get("SUPABASE_SECRET_KEY", "")
APIFY_API_TOKEN = os.environ.get("APIFY_API_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

APIFY_BATCH_SIZE = 50
EMBEDDING_BATCH_SIZE = 100
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
APIFY_ACTOR_ID = "clockworks~tiktok-scraper"
APIFY_POLL_INTERVAL_S = 5
APIFY_MAX_WAIT_S = 600  # 10 minutes

# ---------- DB Engine (module-level, reused across warm invocations) ----------

_engine = None


def _get_engine():
    """Create or return cached sync SQLAlchemy engine."""
    global _engine  # noqa: PLW0603
    if _engine is None:
        url = DATABASE_URL
        # Normalize to sync driver
        if url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
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


def _http_download(
    url: str, headers: dict[str, str], dest_path: str, timeout: int = 120
) -> None:
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


# ==========================================================================
# Step 1: PARSE_EXPORT
# ==========================================================================


def step_parse_export(
    session: Session,
    upload_id: str,
    user_id: str,
    storage_path: str,
    scope: str,
) -> list[str]:
    """Download ZIP from Supabase Storage, parse, upsert media_event rows.

    Returns list of media_event IDs (as strings).
    """
    step_start = time.time()
    logger.info("Step 1/4: parse_export started", extra={"upload_id": upload_id})

    # Mark upload as processing
    session.execute(
        update(Upload).where(Upload.id == UUID(upload_id)).values(status="processing")
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

        # Parse export using existing tiktok_parser
        parsed = parse_tiktok_export(Path(tmp_path), scope=scope)
    finally:
        os.unlink(tmp_path)

    all_refs = parsed.liked_videos + parsed.favorited_videos

    # Update upload total_items
    session.execute(
        update(Upload)
        .where(Upload.id == UUID(upload_id))
        .values(total_items=len(all_refs))
    )

    # Upsert media_event rows with deterministic IDs
    media_event_ids: list[str] = []
    for ref in all_refs:
        platform_id = _extract_platform_id_or_hash(ref.url, upload_id)
        event_id = generate_idempotency_key(upload_id, ref.url)

        stmt = (
            pg_insert(MediaEvent)
            .values(
                id=UUID(event_id),
                user_id=UUID(user_id),
                upload_id=UUID(upload_id),
                platform="tiktok",
                platform_id=platform_id,
                canonical_url=ref.url,
                interaction_type=ref.interaction_type,
                interaction_at=ref.timestamp,
                processing_state="parsed",
            )
            .on_conflict_do_update(
                constraint="uq_media_events_user_platform",
                set_={
                    "interaction_type": ref.interaction_type,
                    "interaction_at": ref.timestamp,
                    # Don't reset processing_state — preserve progress from prior attempts
                    "updated_at": func.now(),
                },
            )
        )
        session.execute(stmt)
        media_event_ids.append(event_id)

    session.commit()

    duration_ms = int((time.time() - step_start) * 1000)
    logger.info(
        "Step 1/4: parse_export complete",
        extra={
            "upload_id": upload_id,
            "items": len(media_event_ids),
            "duration_ms": duration_ms,
        },
    )
    return media_event_ids


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
        logger.warning(
            "Apify run did not succeed", extra={"run_id": run_id, "status": status}
        )
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
        h.get("name", "")
        for h in (apify_data.get("hashtags") or [])
        if isinstance(h, dict)
    ]

    create_time = apify_data.get("createTime")
    video_created_at = (
        datetime.fromtimestamp(int(create_time), tz=timezone.utc)
        if create_time
        else None
    )

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


def step_apify_enrich(
    session: Session,
    upload_id: str,
    media_event_ids: list[str],
    pipeline_run_id: str,
) -> None:
    """Fetch TikTok metadata via Apify scraper in batches of 50."""
    step_start = time.time()
    logger.info("Step 2/4: apify_enrich started", extra={"upload_id": upload_id})

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
            "Step 2/4: no items to enrich (all already enriched)",
            extra={"upload_id": upload_id},
        )
        return

    enriched_count = 0

    for i in range(0, len(events), APIFY_BATCH_SIZE):
        batch = events[i : i + APIFY_BATCH_SIZE]
        urls = [
            _normalize_tiktok_url(e.canonical_url) for e in batch if e.canonical_url
        ]

        apify_items = _run_apify_batch(urls)

        # Index Apify results by video ID for matching
        results_by_pid: dict[str, dict] = {}
        for item in apify_items:
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

            values = _map_apify_to_update(apify_data)
            session.execute(
                update(MediaEvent).where(MediaEvent.id == event.id).values(**values)
            )
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
        "Step 2/4: apify_enrich complete",
        extra={
            "upload_id": upload_id,
            "enriched": enriched_count,
            "duration_ms": duration_ms,
        },
    )


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
    logger.info("Step 3/4: subtitle_fetch started", extra={"upload_id": upload_id})

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
        "Step 3/4: subtitle_fetch complete",
        extra={
            "upload_id": upload_id,
            "subtitled": len(events),
            "duration_ms": duration_ms,
        },
    )


# ==========================================================================
# Step 4: EMBEDDING
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
    return " | ".join(parts) if parts else "untitled tiktok"


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
    logger.info("Step 4/4: embed started", extra={"upload_id": upload_id})

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
        logger.info("Step 4/4: no items to embed", extra={"upload_id": upload_id})
        return

    # Fuse text and store full_text
    texts: list[str] = []
    ordered_events: list[MediaEvent] = []
    for event in events:
        full_text = _fuse_text(event)
        session.execute(
            update(MediaEvent)
            .where(MediaEvent.id == event.id)
            .values(full_text=full_text)
        )
        texts.append(full_text)
        ordered_events.append(event)

    # Batch embed
    embedded_count = 0
    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch_texts = texts[i : i + EMBEDDING_BATCH_SIZE]
        batch_events = ordered_events[i : i + EMBEDDING_BATCH_SIZE]

        vectors = _embed_batch(batch_texts)

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
        "Step 4/4: embed complete",
        extra={
            "upload_id": upload_id,
            "embedded": embedded_count,
            "duration_ms": duration_ms,
        },
    )


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
        started_at=datetime.now(timezone.utc),
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
                update(Upload)
                .where(Upload.id == UUID(upload_id))
                .values(status="failed")
            )
            session.execute(
                update(UploadPipelineRun)
                .where(
                    UploadPipelineRun.upload_id == UUID(upload_id),
                    UploadPipelineRun.status == "processing",
                )
                .values(status="failed", finished_at=datetime.now(timezone.utc))
            )
            session.commit()
        finally:
            session.close()
    except Exception:
        logger.exception(
            "Failed to mark upload as failed", extra={"upload_id": upload_id}
        )


# ==========================================================================
# Lambda Entry Point
# ==========================================================================


def handler(event: dict, context: Any) -> dict:
    """Lambda handler: processes one SQS message through 4 pipeline steps.

    Expected SQS message body:
        {
            "upload_id": "uuid",
            "user_id": "uuid",
            "storage_path": "uploads/{user_id}/{upload_id}/export.zip",
            "scope": "both"  // "liked", "favorited", or "both"
        }
    """
    records = event.get("Records", [])
    if not records:
        return {"statusCode": 200, "body": "No records"}

    record = records[0]
    body = json.loads(record["body"])

    upload_id: str = body["upload_id"]
    user_id: str = body["user_id"]
    storage_path: str = body["storage_path"]
    scope: str = body.get("scope", "both")

    request_id = getattr(context, "aws_request_id", "local") if context else "local"

    logger.info(
        "Pipeline started",
        extra={"upload_id": upload_id, "request_id": request_id, "scope": scope},
    )

    start = time.time()
    session = _session()

    try:
        # Create/get pipeline run
        pipeline_run_id = _ensure_pipeline_run(session, upload_id, user_id)
        session.commit()

        # Step 1: Parse export -> create media_event rows
        media_event_ids = step_parse_export(
            session, upload_id, user_id, storage_path, scope
        )

        # Update pipeline run total
        session.execute(
            update(UploadPipelineRun)
            .where(UploadPipelineRun.id == UUID(pipeline_run_id))
            .values(total_items=len(media_event_ids))
        )
        session.commit()

        # Step 2: Apify enrich -> fetch TikTok metadata
        step_apify_enrich(session, upload_id, media_event_ids, pipeline_run_id)

        # Step 3: Subtitle fetch -> extract subtitles
        step_subtitle_fetch(session, upload_id, media_event_ids, pipeline_run_id)

        # Step 4: Embed -> generate search embeddings
        step_embed(session, upload_id, media_event_ids, pipeline_run_id)

        # Mark upload + pipeline run as complete
        session.execute(
            update(Upload)
            .where(Upload.id == UUID(upload_id))
            .values(
                status="complete",
                processed_items=len(media_event_ids),
                completed_at=datetime.now(timezone.utc),
            )
        )
        session.execute(
            update(UploadPipelineRun)
            .where(UploadPipelineRun.id == UUID(pipeline_run_id))
            .values(status="complete", finished_at=datetime.now(timezone.utc))
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
