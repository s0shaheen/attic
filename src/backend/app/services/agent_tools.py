"""Agent tool functions for the Claude orchestrator.

Each tool function is called by the agent loop when Claude invokes a tool.
All tools return AgentToolResult (never raise). Results are cached to DB inline.

Tools:
- query_items: Search/filter user's media_events via SQLAlchemy.
- resolve_entity: Resolve an entity (place, book, movie, music) via external APIs.
- search_similar: Semantic search via pgvector cosine similarity.
- get_stats: Aggregate statistics on user's media events.
  Stat types: overview, top_creators, top_hashtags, interaction_timeline,
  classification_breakdown, creator_details, field_distribution.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.media_event import MediaEvent
from app.services.entity_resolvers import resolve_entity as _resolve_entity

# NOTE: gemini classify/analyze_visual imports removed — pipeline handles all enrichment

logger = logging.getLogger(__name__)

# Limits
MAX_QUERY_RESULTS = 50


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class AgentToolResult:
    """Unified result type for all agent tools."""

    success: bool
    data: Any = None
    error: str | None = None
    partial_data: Any = None  # Available even on failure (e.g., partial results)


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

_TOOL_REGISTRY: dict[str, dict[str, Any]] = {}


def tool(name: str, description: str, input_schema: dict):
    """Register a tool function with its Anthropic API schema.

    Usage:
        @tool("my_tool", description="...", input_schema={...})
        async def my_tool(...) -> AgentToolResult:
            ...
    """

    def decorator(fn):
        _TOOL_REGISTRY[name] = {
            "fn": fn,
            "schema": {
                "name": name,
                "description": description,
                "input_schema": input_schema,
            },
        }
        return fn

    return decorator


def get_tool_definitions() -> list[dict]:
    """Return Anthropic-formatted tool definitions for all registered tools."""
    return [entry["schema"] for entry in _TOOL_REGISTRY.values()]


# ---------------------------------------------------------------------------
# Tool: query_items
# ---------------------------------------------------------------------------


@tool(
    "query_items",
    description=(
        "Search and filter the user's saved social media content. "
        "Supports text search, hashtag filtering, creator filtering, "
        "and classification-based filters. Returns matching items with metadata."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "search_text": {
                "type": "string",
                "description": "Full-text search across captions, subtitles, and text content.",
            },
            "hashtag": {
                "type": "string",
                "description": "Filter by hashtag (e.g., 'cooking').",
            },
            "creator": {
                "type": "string",
                "description": "Filter by creator username.",
            },
            "topic": {
                "type": "string",
                "description": "Filter by classification topic (e.g., 'food', 'fitness').",
            },
            "affect": {
                "type": "string",
                "description": "Filter by affect/mood (e.g., 'funny', 'inspiring').",
            },
            "genre": {
                "type": "string",
                "description": "Filter by content genre (e.g., 'tutorial', 'recipe').",
            },
            "media_type": {
                "type": "string",
                "enum": ["video", "image", "slideshow"],
                "description": "Filter by media type.",
            },
            "limit": {
                "type": "integer",
                "description": "Max results to return (default 20, max 50).",
            },
            "offset": {
                "type": "integer",
                "description": "Offset for pagination.",
            },
        },
    },
)
async def query_items(
    db: AsyncSession,
    user_id: UUID,
    *,
    search_text: str | None = None,
    hashtag: str | None = None,
    creator: str | None = None,
    topic: str | None = None,
    affect: str | None = None,
    genre: str | None = None,
    media_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> AgentToolResult:
    """Query user's media events with flexible filtering.

    Args:
        db: Async database session.
        user_id: The user's ID (for isolation).
        search_text: Full-text search in caption, subtitle, full_text.
        hashtag: Filter by hashtag (partial match).
        creator: Filter by creator username.
        topic: Filter by cached classification topic.
        affect: Filter by cached classification affect.
        genre: Filter by cached classification genre.
        media_type: Filter by media type (video, image, slideshow).
        limit: Max results (capped at MAX_QUERY_RESULTS).
        offset: Offset for pagination.

    Returns:
        AgentToolResult with list of matching items.
    """
    try:
        limit = min(limit, MAX_QUERY_RESULTS)

        stmt = select(MediaEvent).where(MediaEvent.user_id == user_id)

        if search_text:
            pattern = f"%{search_text}%"
            stmt = stmt.where(
                or_(
                    MediaEvent.caption_text.ilike(pattern),
                    MediaEvent.subtitle_text.ilike(pattern),
                    MediaEvent.full_text.ilike(pattern),
                )
            )

        if hashtag:
            # Array contains check — cast hashtag array elements
            stmt = stmt.where(MediaEvent.hashtags.any(hashtag.lower()))

        if creator:
            stmt = stmt.where(MediaEvent.creator_username.ilike(f"%{creator}%"))

        if topic:
            # Query cached_classifications JSONB — tier1 structure, astext for unquoted
            stmt = stmt.where(MediaEvent.cached_classifications["tier1"]["topic"].astext == topic)

        if affect:
            stmt = stmt.where(MediaEvent.cached_classifications["tier1"]["affect"].astext == affect)

        if genre:
            stmt = stmt.where(MediaEvent.cached_classifications["tier1"]["genre"].astext == genre)

        if media_type:
            stmt = stmt.where(MediaEvent.media_type == media_type)

        # Get total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0

        # Get results
        stmt = stmt.order_by(MediaEvent.interaction_at.desc().nulls_last())
        stmt = stmt.offset(offset).limit(limit)

        result = await db.execute(stmt)
        rows = result.scalars().all()

        items = []
        for row in rows:
            items.append(
                {
                    "id": str(row.id),
                    "caption": row.caption_text,
                    "creator": row.creator_username,
                    "hashtags": row.hashtags or [],
                    "media_type": row.media_type,
                    "interaction_type": row.interaction_type,
                    "interaction_at": row.interaction_at.isoformat()
                    if row.interaction_at
                    else None,
                    "thumbnail_url": row.thumbnail_url,
                    "music_name": row.music_name,
                    "cached_classifications": row.cached_classifications,
                    "cached_entities": row.cached_entities,
                    "play_count": row.play_count,
                    "like_count": row.like_count,
                }
            )

        return AgentToolResult(
            success=True,
            data={"items": items, "total": total, "limit": limit, "offset": offset},
        )

    except Exception as e:
        logger.error({"event": "query_items_error", "error": str(e), "user_id": str(user_id)})
        return AgentToolResult(success=False, error=f"Database query failed: {e}")


# NOTE: classify tool removed — classification is handled by the pipeline only.
# The agent reads cached_classifications from items already processed by the pipeline.


# NOTE: analyze_visual tool removed — visual perception is handled by the pipeline only.
# The agent reads perception data from cached_classifications.perception.


# ---------------------------------------------------------------------------
# Tool: resolve_entity
# ---------------------------------------------------------------------------


@tool(
    "resolve_entity",
    description=(
        "Resolve a named entity (place, book, movie, TV show, song) "
        "mentioned in a media event. Returns structured metadata from "
        "Google Maps, Google Books, TMDB, or Spotify. "
        "Results are cached on the media event."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "media_event_id": {
                "type": "string",
                "description": "UUID of the media event the entity was found in.",
            },
            "entity_type": {
                "type": "string",
                "enum": [
                    "place",
                    "restaurant",
                    "location",
                    "book",
                    "movie",
                    "tv",
                    "tv_show",
                    "show",
                    "music",
                    "song",
                    "artist",
                ],
                "description": "Type of entity to resolve.",
            },
            "entity_query": {
                "type": "string",
                "description": "The name/surface form to search for (e.g., 'Atomic Habits').",
            },
        },
        "required": ["media_event_id", "entity_type", "entity_query"],
    },
)
async def resolve_entity(
    db: AsyncSession,
    settings: Settings,
    media_event_id: UUID,
    user_id: UUID,
    entity_type: str,
    entity_query: str,
) -> AgentToolResult:
    """Resolve an entity and cache the result on the media event.

    Args:
        db: Async database session.
        settings: Application settings (for API keys).
        media_event_id: The media event this entity belongs to.
        user_id: The user's ID (for isolation).
        entity_type: Type of entity (place, book, movie, music, etc.).
        entity_query: Surface-form text to resolve.

    Returns:
        AgentToolResult with resolved entity data.
    """
    try:
        # Fetch the media event
        stmt = select(MediaEvent).where(
            MediaEvent.id == media_event_id,
            MediaEvent.user_id == user_id,
        )
        result = await db.execute(stmt)
        event = result.scalar_one_or_none()

        if event is None:
            return AgentToolResult(success=False, error="Media event not found")

        # Check if already cached
        existing_entities = event.cached_entities or []
        for ent in existing_entities:
            if (
                isinstance(ent, dict)
                and ent.get("surface", "").lower() == entity_query.lower()
                and ent.get("entity_type") == entity_type
            ):
                return AgentToolResult(success=True, data=ent)

        # Resolve via external API
        resolution = await _resolve_entity(
            entity_type=entity_type,
            query=entity_query,
            google_maps_api_key=settings.google_maps_api_key,
            google_books_api_key=settings.google_books_api_key,
            tmdb_api_key=settings.tmdb_api_key,
            spotify_client_id=settings.spotify_client_id,
            spotify_client_secret=settings.spotify_client_secret,
        )

        if not resolution.success:
            return AgentToolResult(success=False, error=resolution.error)

        entity = resolution.entity
        entity_data = {
            "entity_type": entity.entity_type,
            "surface": entity.surface,
            "name": entity.name,
            "metadata": entity.metadata,
        }

        # Cache to DB — append to existing entities
        updated_entities = list(existing_entities) + [entity_data]
        event.cached_entities = updated_entities
        await db.flush()

        return AgentToolResult(success=True, data=entity_data)

    except Exception as e:
        logger.error(
            {"event": "resolve_entity_error", "error": str(e), "entity_query": entity_query}
        )
        return AgentToolResult(success=False, error=f"Entity resolution failed: {e}")


# ---------------------------------------------------------------------------
# Tool: search_similar
# ---------------------------------------------------------------------------

# Reusable httpx client for OpenAI embedding calls
_openai_client: httpx.AsyncClient | None = None

OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_EMBEDDING_DIMENSIONS = 1536
MAX_SEARCH_RESULTS = 50


def _get_openai_client() -> httpx.AsyncClient:
    """Get or create shared httpx client for OpenAI API."""
    global _openai_client
    if _openai_client is None:
        _openai_client = httpx.AsyncClient(
            base_url="https://api.openai.com/v1",
            timeout=10.0,
        )
    return _openai_client


_EMBED_RETRYABLE_STATUSES = {429, 500, 502, 503}
_EMBED_MAX_RETRIES = 3
_EMBED_BACKOFF = [1, 2, 4]


async def _embed_query(api_key: str, text: str) -> list[float] | None:
    """Embed a query string via OpenAI embeddings API.

    Retries on 429/5xx with exponential backoff. Returns the embedding
    vector or None on failure.
    """
    client = _get_openai_client()
    start = time.monotonic()

    for attempt in range(_EMBED_MAX_RETRIES + 1):
        resp = await client.post(
            "/embeddings",
            json={
                "model": OPENAI_EMBEDDING_MODEL,
                "input": text,
                "dimensions": OPENAI_EMBEDDING_DIMENSIONS,
            },
            headers={"Authorization": f"Bearer {api_key}"},
        )

        if resp.status_code not in _EMBED_RETRYABLE_STATUSES:
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["embedding"]

        if attempt == _EMBED_MAX_RETRIES:
            resp.raise_for_status()  # raise on final failure

        # Backoff with Retry-After support
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                wait = min(float(retry_after), 30)
            except ValueError:
                wait = _EMBED_BACKOFF[attempt]
        else:
            wait = _EMBED_BACKOFF[attempt]

        # Cap total retry time at 30s
        if time.monotonic() - start + wait > 30:
            resp.raise_for_status()

        logger.warning(
            {
                "event": "openai_embedding_retry",
                "status": resp.status_code,
                "attempt": attempt + 1,
                "wait_seconds": wait,
            }
        )
        await asyncio.sleep(wait)

    return None  # unreachable but satisfies type checker


@tool(
    "search_similar",
    description=(
        "Search for media events semantically similar to a text query. "
        "Uses AI embeddings to find items matching the meaning of the query, "
        "not just keyword matches. Good for queries like 'something relaxing' "
        "or 'funny cooking fails'."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query_text": {
                "type": "string",
                "description": (
                    "The text to search for semantically (e.g., 'relaxing nature content')."
                ),
            },
            "limit": {
                "type": "integer",
                "description": "Max results to return (default 10, max 50).",
            },
        },
        "required": ["query_text"],
    },
)
async def search_similar(
    db: AsyncSession,
    settings: Settings,
    user_id: UUID,
    *,
    query_text: str,
    limit: int = 10,
) -> AgentToolResult:
    """Semantic search over user's media events using pgvector cosine similarity.

    Args:
        db: Async database session.
        settings: Application settings (for OpenAI API key).
        user_id: The user's ID (for isolation).
        query_text: Text to embed and search for.
        limit: Max results (capped at MAX_SEARCH_RESULTS).

    Returns:
        AgentToolResult with list of similar items and similarity scores.
    """
    try:
        limit = min(limit, MAX_SEARCH_RESULTS)

        # Check if user has any embedded items
        count_stmt = select(func.count()).select_from(
            select(MediaEvent.id)
            .where(MediaEvent.user_id == user_id)
            .where(MediaEvent.embedding_vector.isnot(None))
            .subquery()
        )
        embedded_count = (await db.execute(count_stmt)).scalar() or 0

        if embedded_count == 0:
            return AgentToolResult(
                success=True,
                data={
                    "items": [],
                    "total_embedded": 0,
                    "note": "Your data is still being processed — semantic search "
                    "will be available once the pipeline completes embedding generation.",
                },
            )

        # Dev mode fallback: no OpenAI key means random embeddings, skip vector search
        if not settings.openai_api_key:
            logger.info({"event": "search_similar_fallback_recency", "reason": "no_openai_key"})
            fallback_stmt = (
                select(MediaEvent)
                .where(MediaEvent.user_id == user_id)
                .where(MediaEvent.processing_state == "complete")
                .order_by(MediaEvent.interaction_at.desc())
                .limit(limit)
            )
            fallback_result = await db.execute(fallback_stmt)
            fallback_rows = fallback_result.scalars().all()
            items = [
                {
                    "id": str(e.id),
                    "caption": e.caption_text,
                    "creator": e.creator_username,
                    "hashtags": e.hashtags,
                    "media_type": e.media_type,
                    "interaction_type": e.interaction_type,
                    "interaction_at": e.interaction_at.isoformat() if e.interaction_at else None,
                    "similarity": None,
                }
                for e in fallback_rows
            ]
            return AgentToolResult(
                success=True,
                data={
                    "items": items,
                    "total_results": len(items),
                    "note": "Semantic search unavailable in dev mode (no OpenAI key). "
                    "Results sorted by recency instead.",
                },
            )

        # Embed the query text
        try:
            query_embedding = await _embed_query(settings.openai_api_key, query_text)
        except Exception as e:
            logger.error({"event": "search_similar_embed_error", "error": str(e)})
            return AgentToolResult(
                success=False, error="Failed to generate search embedding. Please try again."
            )

        if query_embedding is None:
            return AgentToolResult(success=False, error="Failed to generate search embedding.")

        # pgvector cosine distance search
        # Using raw SQL for the <=> operator since SQLAlchemy doesn't natively support it
        embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"
        similarity_stmt = text(
            """
            SELECT id, caption_text, creator_username, hashtags, media_type,
                   interaction_type, interaction_at, thumbnail_url, music_name,
                   canonical_url, play_count, like_count,
                   cached_classifications, cached_entities,
                   (embedding_vector <=> CAST(:query_vec AS vector)) AS distance
            FROM media_events
            WHERE user_id = :uid AND embedding_vector IS NOT NULL
            ORDER BY distance ASC
            LIMIT :lim
            """
        )

        result = await db.execute(
            similarity_stmt,
            {"query_vec": embedding_str, "uid": str(user_id), "lim": limit},
        )
        rows = result.mappings().all()

        items = []
        for row in rows:
            similarity = 1.0 - float(row["distance"])  # cosine distance → similarity
            items.append(
                {
                    "id": str(row["id"]),
                    "caption": row["caption_text"],
                    "creator": row["creator_username"],
                    "hashtags": row["hashtags"] or [],
                    "media_type": row["media_type"],
                    "interaction_type": row["interaction_type"],
                    "interaction_at": row["interaction_at"].isoformat()
                    if row["interaction_at"]
                    else None,
                    "thumbnail_url": row["thumbnail_url"],
                    "canonical_url": row["canonical_url"],
                    "music_name": row["music_name"],
                    "play_count": row["play_count"],
                    "like_count": row["like_count"],
                    "cached_classifications": row["cached_classifications"],
                    "similarity": round(similarity, 4),
                }
            )

        return AgentToolResult(
            success=True,
            data={"items": items, "total_embedded": embedded_count, "query": query_text},
        )

    except Exception as e:
        logger.error({"event": "search_similar_error", "error": str(e), "user_id": str(user_id)})
        return AgentToolResult(success=False, error=f"Semantic search failed: {e}")


# ---------------------------------------------------------------------------
# Tool: get_stats
# ---------------------------------------------------------------------------

_VALID_STAT_TYPES = frozenset(
    {
        "overview",
        "top_creators",
        "top_hashtags",
        "interaction_timeline",
        "classification_breakdown",
        "creator_details",
        "field_distribution",
    }
)

_AGGREGATE_FIELDS = frozenset({"music_name", "creator_username", "media_type", "interaction_type"})


@tool(
    "get_stats",
    description=(
        "Get aggregate statistics about the user's saved social media content. "
        "Use this for high-level insights like 'what's my feed about?', "
        "'who are my top creators?', or 'how has my usage changed over time?'."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "stat_type": {
                "type": "string",
                "enum": list(_VALID_STAT_TYPES),
                "description": (
                    "Type of statistic to compute: "
                    "'overview' (total items, date range, media types), "
                    "'top_creators' (top 20 creators by count), "
                    "'top_hashtags' (top 30 hashtags by frequency), "
                    "'interaction_timeline' (items per month over time), "
                    "'classification_breakdown' (distribution of cached classifications), "
                    "'creator_details' (top 20 creators with date ranges and top topics), "
                    "'field_distribution' (value counts for a specific field — "
                    "requires 'field' param)."
                ),
            },
            "field": {
                "type": "string",
                "enum": list(_AGGREGATE_FIELDS),
                "description": (
                    "Required when stat_type is 'field_distribution'. The field to group by."
                ),
            },
        },
        "required": ["stat_type"],
    },
)
async def get_stats(
    db: AsyncSession,
    user_id: UUID,
    *,
    stat_type: str,
    field: str | None = None,
) -> AgentToolResult:
    """Compute aggregate statistics on user's media events.

    Args:
        db: Async database session.
        user_id: The user's ID (for isolation).
        stat_type: Which statistic to compute.
        field: Required when stat_type is 'field_distribution'. The field to group by.

    Returns:
        AgentToolResult with the requested statistics.
    """
    try:
        if stat_type not in _VALID_STAT_TYPES:
            return AgentToolResult(
                success=False,
                error=f"Unknown stat_type '{stat_type}'. "
                f"Valid types: {', '.join(sorted(_VALID_STAT_TYPES))}",
            )

        if stat_type == "field_distribution":
            if not field:
                return AgentToolResult(
                    success=False,
                    error="'field' is required when stat_type is 'field_distribution'. "
                    f"Valid fields: {', '.join(sorted(_AGGREGATE_FIELDS))}",
                )
            if field not in _AGGREGATE_FIELDS:
                return AgentToolResult(
                    success=False,
                    error=f"Invalid field '{field}'. "
                    f"Valid fields: {', '.join(sorted(_AGGREGATE_FIELDS))}",
                )
            return await _stats_field_distribution(db, user_id, field)

        if stat_type == "overview":
            return await _stats_overview(db, user_id)
        elif stat_type == "top_creators":
            return await _stats_top_creators(db, user_id)
        elif stat_type == "top_hashtags":
            return await _stats_top_hashtags(db, user_id)
        elif stat_type == "interaction_timeline":
            return await _stats_interaction_timeline(db, user_id)
        elif stat_type == "classification_breakdown":
            return await _stats_classification_breakdown(db, user_id)
        elif stat_type == "creator_details":
            return await _stats_creator_details(db, user_id)

        # Unreachable, but satisfies exhaustiveness
        return AgentToolResult(success=False, error="Unknown stat type")

    except Exception as e:
        logger.error({"event": "get_stats_error", "error": str(e), "stat_type": stat_type})
        return AgentToolResult(success=False, error=f"Stats query failed: {e}")


async def _stats_overview(db: AsyncSession, user_id: UUID) -> AgentToolResult:
    """Total items, date range, media type breakdown."""
    stmt = text(
        """
        SELECT
            COUNT(*) AS total_items,
            MIN(interaction_at) AS earliest,
            MAX(interaction_at) AS latest,
            COUNT(*) FILTER (WHERE media_type = 'video') AS video_count,
            COUNT(*) FILTER (WHERE media_type = 'image') AS image_count,
            COUNT(*) FILTER (WHERE media_type = 'slideshow') AS slideshow_count,
            COUNT(DISTINCT creator_username) AS unique_creators,
            COUNT(*) FILTER (WHERE embedding_vector IS NOT NULL) AS embedded_count
        FROM media_events
        WHERE user_id = :uid
        """
    )
    result = await db.execute(stmt, {"uid": str(user_id)})
    row = result.mappings().one()

    return AgentToolResult(
        success=True,
        data={
            "total_items": row["total_items"],
            "date_range": {
                "earliest": row["earliest"].isoformat() if row["earliest"] else None,
                "latest": row["latest"].isoformat() if row["latest"] else None,
            },
            "media_types": {
                "video": row["video_count"],
                "image": row["image_count"],
                "slideshow": row["slideshow_count"],
            },
            "unique_creators": row["unique_creators"],
            "embedded_count": row["embedded_count"],
        },
    )


async def _stats_top_creators(db: AsyncSession, user_id: UUID) -> AgentToolResult:
    """Top 20 creators by item count."""
    stmt = text(
        """
        SELECT creator_username, COUNT(*) AS item_count
        FROM media_events
        WHERE user_id = :uid AND creator_username IS NOT NULL
        GROUP BY creator_username
        ORDER BY item_count DESC
        LIMIT 20
        """
    )
    result = await db.execute(stmt, {"uid": str(user_id)})
    rows = result.mappings().all()

    creators = [{"creator": row["creator_username"], "count": row["item_count"]} for row in rows]
    return AgentToolResult(success=True, data={"creators": creators})


async def _stats_top_hashtags(db: AsyncSession, user_id: UUID) -> AgentToolResult:
    """Top 30 hashtags by frequency."""
    stmt = text(
        """
        SELECT tag, COUNT(*) AS frequency
        FROM media_events, UNNEST(hashtags) AS tag
        WHERE user_id = :uid
        GROUP BY tag
        ORDER BY frequency DESC
        LIMIT 30
        """
    )
    result = await db.execute(stmt, {"uid": str(user_id)})
    rows = result.mappings().all()

    hashtags = [{"hashtag": row["tag"], "count": row["frequency"]} for row in rows]
    return AgentToolResult(success=True, data={"hashtags": hashtags})


async def _stats_interaction_timeline(db: AsyncSession, user_id: UUID) -> AgentToolResult:
    """Items per month over time."""
    stmt = text(
        """
        SELECT
            date_trunc('month', interaction_at) AS month,
            COUNT(*) AS item_count
        FROM media_events
        WHERE user_id = :uid AND interaction_at IS NOT NULL
        GROUP BY month
        ORDER BY month ASC
        """
    )
    result = await db.execute(stmt, {"uid": str(user_id)})
    rows = result.mappings().all()

    timeline = [
        {"month": row["month"].isoformat() if row["month"] else None, "count": row["item_count"]}
        for row in rows
    ]
    return AgentToolResult(success=True, data={"timeline": timeline})


async def _stats_classification_breakdown(db: AsyncSession, user_id: UUID) -> AgentToolResult:
    """Distribution of cached classifications with coverage context."""
    # Get total and classified counts
    count_stmt = text(
        """
        SELECT
            COUNT(*) AS total_count,
            COUNT(*) FILTER (WHERE cached_classifications IS NOT NULL) AS classified_count
        FROM media_events
        WHERE user_id = :uid
        """
    )
    count_result = await db.execute(count_stmt, {"uid": str(user_id)})
    counts = count_result.mappings().one()

    total = counts["total_count"]
    classified = counts["classified_count"]

    if classified == 0:
        return AgentToolResult(
            success=True,
            data={
                "classified_count": 0,
                "total_count": total,
                "coverage_pct": 0.0,
                "note": "No items have been classified yet. Ask me to classify some items first!",
                "distributions": {},
            },
        )

    # Get distributions for key facets from tier1 structure
    facet_stmt = text(
        """
        SELECT
            facet.key AS facet,
            facet.value #>> '{}' AS label,
            COUNT(*) AS count
        FROM media_events,
             jsonb_each(cached_classifications->'tier1') AS facet(key, value)
        WHERE user_id = :uid
          AND cached_classifications IS NOT NULL
          AND cached_classifications->'tier1' IS NOT NULL
          AND facet.key = ANY(:facets)
          AND facet.value #>> '{}' IS NOT NULL
        GROUP BY facet.key, label
        ORDER BY facet.key, count DESC
        """
    )
    facet_result = await db.execute(
        facet_stmt,
        {"uid": str(user_id), "facets": ["topic", "affect", "genre"]},
    )
    facet_rows = facet_result.mappings().all()

    distributions: dict[str, list[dict]] = {}
    for row in facet_rows:
        facet_name = row["facet"]
        if facet_name not in distributions:
            distributions[facet_name] = []
        distributions[facet_name].append({"label": row["label"], "count": row["count"]})

    coverage_pct = round((classified / total) * 100, 1) if total > 0 else 0.0

    return AgentToolResult(
        success=True,
        data={
            "classified_count": classified,
            "total_count": total,
            "coverage_pct": coverage_pct,
            "distributions": distributions,
        },
    )


async def _stats_creator_details(db: AsyncSession, user_id: UUID) -> AgentToolResult:
    """Top 20 creators with item counts, date ranges, and top cached topics.

    Two sequential queries:
    1. Top creators by count + date range (GROUP BY creator_username)
    2. Bulk topic fetch for those creators from cached_classifications JSONB
    """
    # Query 1: Top 20 creators with counts and date range
    creators_stmt = text(
        """
        SELECT creator_username,
               COUNT(*) AS item_count,
               MIN(interaction_at) AS first_seen,
               MAX(interaction_at) AS last_seen
        FROM media_events
        WHERE user_id = :uid AND creator_username IS NOT NULL
        GROUP BY creator_username
        ORDER BY item_count DESC
        LIMIT 20
        """
    )
    result = await db.execute(creators_stmt, {"uid": str(user_id)})
    creator_rows = result.mappings().all()

    if not creator_rows:
        return AgentToolResult(
            success=True,
            data={
                "creators": [],
                "note": "No creator data found. Your items may not have creator information.",
            },
        )

    # Build base creator list
    creator_names = [row["creator_username"] for row in creator_rows]
    creators = {
        row["creator_username"]: {
            "creator": row["creator_username"],
            "count": row["item_count"],
            "first_seen": row["first_seen"].isoformat() if row["first_seen"] else None,
            "last_seen": row["last_seen"].isoformat() if row["last_seen"] else None,
            "top_topics": [],
        }
        for row in creator_rows
    }

    # Query 2: Bulk topic fetch for top creators (tier1 structure)
    topics_stmt = text(
        """
        SELECT creator_username,
               cached_classifications->'tier1'->>'topic' AS topic,
               COUNT(*) AS topic_count
        FROM media_events
        WHERE user_id = :uid
          AND creator_username = ANY(:creators)
          AND cached_classifications->'tier1'->>'topic' IS NOT NULL
        GROUP BY creator_username, topic
        ORDER BY creator_username, topic_count DESC
        """
    )
    topic_result = await db.execute(
        topics_stmt,
        {"uid": str(user_id), "creators": creator_names},
    )
    topic_rows = topic_result.mappings().all()

    # Post-process: top 3 topics per creator
    for row in topic_rows:
        creator = row["creator_username"]
        if creator in creators and len(creators[creator]["top_topics"]) < 3:
            creators[creator]["top_topics"].append(
                {"topic": row["topic"], "count": row["topic_count"]}
            )

    # Return in original rank order
    ordered = [creators[name] for name in creator_names]
    return AgentToolResult(success=True, data={"creators": ordered})


async def _stats_field_distribution(db: AsyncSession, user_id: UUID, field: str) -> AgentToolResult:
    """Value counts for a specific field (GROUP BY + COUNT + ORDER BY count DESC).

    Field name is validated against _AGGREGATE_FIELDS before this function is called,
    so the f-string injection is safe.
    """
    # Safe: field is validated against _AGGREGATE_FIELDS allowlist in get_stats()
    stmt = text(
        f"""
        SELECT {field} AS field_value, COUNT(*) AS item_count
        FROM media_events
        WHERE user_id = :uid AND {field} IS NOT NULL
        GROUP BY {field}
        ORDER BY item_count DESC
        LIMIT 30
        """
    )
    result = await db.execute(stmt, {"uid": str(user_id)})
    rows = result.mappings().all()

    if not rows:
        return AgentToolResult(
            success=True,
            data={
                "field": field,
                "distribution": [],
                "note": f"No data found for field '{field}'.",
            },
        )

    distribution = [{"value": row["field_value"], "count": row["item_count"]} for row in rows]
    return AgentToolResult(success=True, data={"field": field, "distribution": distribution})
