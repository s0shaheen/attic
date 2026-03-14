"""Agent tool functions for the Claude orchestrator.

Each tool function is called by the agent loop when Claude invokes a tool.
All tools return AgentToolResult (never raise). Results are cached to DB inline.

Tools:
- query_items: Search/filter user's media_events via SQLAlchemy.
- classify: Classify a media event using Gemini 3 Flash.
- analyze_visual: Analyze a thumbnail with Gemini vision + grounding.
- resolve_entity: Resolve an entity (place, book, movie, music) via external APIs.
"""

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.media_event import MediaEvent
from app.services.entity_resolvers import resolve_entity as _resolve_entity
from app.services.gemini import analyze_visual as gemini_analyze
from app.services.gemini import classify as gemini_classify
from app.services.ontology import validate_classification

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
# Tool: query_items
# ---------------------------------------------------------------------------


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
            # Query cached_classifications JSONB
            stmt = stmt.where(
                cast(MediaEvent.cached_classifications["topic"]["label"], String) == topic
            )

        if affect:
            stmt = stmt.where(
                cast(MediaEvent.cached_classifications["affect"]["label"], String) == affect
            )

        if genre:
            stmt = stmt.where(
                cast(MediaEvent.cached_classifications["genre"]["label"], String) == genre
            )

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


# ---------------------------------------------------------------------------
# Tool: classify
# ---------------------------------------------------------------------------


async def classify(
    db: AsyncSession,
    settings: Settings,
    media_event_id: UUID,
    user_id: UUID,
) -> AgentToolResult:
    """Classify a media event using Gemini, cache result to DB.

    If cached_classifications already exists on the row, returns the cache.

    Args:
        db: Async database session.
        settings: Application settings (for API keys).
        media_event_id: The media event to classify.
        user_id: The user's ID (for isolation).

    Returns:
        AgentToolResult with ClassificationResult data.
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

        # Check cache
        if event.cached_classifications:
            return AgentToolResult(success=True, data=event.cached_classifications)

        # Call Gemini
        gemini_result = await gemini_classify(
            api_key=settings.gemini_api_key,
            caption=event.caption_text,
            subtitle=event.subtitle_text,
            hashtags=event.hashtags,
            creator_username=event.creator_username,
            music_name=event.music_name,
        )

        if not gemini_result.success:
            return AgentToolResult(success=False, error=gemini_result.error)

        # Validate through ontology
        validated = validate_classification(gemini_result.raw_classification or {})

        # Build cache payload
        cache = {
            "tier1": validated.tier1,
            "tier2": validated.tier2,
            "confidence": validated.confidence,
        }

        # Write back to DB (upsert pattern — just update the column)
        event.cached_classifications = cache
        await db.flush()

        return AgentToolResult(success=True, data=cache)

    except Exception as e:
        logger.error(
            {"event": "classify_error", "error": str(e), "media_event_id": str(media_event_id)}
        )
        return AgentToolResult(success=False, error=f"Classification failed: {e}")


# ---------------------------------------------------------------------------
# Tool: analyze_visual
# ---------------------------------------------------------------------------


async def analyze_visual(
    db: AsyncSession,
    settings: Settings,
    media_event_id: UUID,
    user_id: UUID,
) -> AgentToolResult:
    """Analyze a media event's thumbnail using Gemini vision.

    Args:
        db: Async database session.
        settings: Application settings (for API keys).
        media_event_id: The media event whose thumbnail to analyze.
        user_id: The user's ID (for isolation).

    Returns:
        AgentToolResult with visual analysis data.
    """
    try:
        stmt = select(MediaEvent).where(
            MediaEvent.id == media_event_id,
            MediaEvent.user_id == user_id,
        )
        result = await db.execute(stmt)
        event = result.scalar_one_or_none()

        if event is None:
            return AgentToolResult(success=False, error="Media event not found")

        if not event.thumbnail_url:
            return AgentToolResult(success=False, error="No thumbnail available for this item")

        # Call Gemini vision
        visual_result = await gemini_analyze(
            api_key=settings.gemini_api_key,
            image_url=event.thumbnail_url,
            caption=event.caption_text,
        )

        if not visual_result.success:
            return AgentToolResult(success=False, error=visual_result.error)

        data = {
            "description": visual_result.description,
            "objects": visual_result.objects,
            "text_detected": visual_result.text_detected,
            "grounding_sources": visual_result.grounding_sources,
        }

        return AgentToolResult(success=True, data=data)

    except Exception as e:
        logger.error(
            {
                "event": "analyze_visual_error",
                "error": str(e),
                "media_event_id": str(media_event_id),
            }
        )
        return AgentToolResult(success=False, error=f"Visual analysis failed: {e}")


# ---------------------------------------------------------------------------
# Tool: resolve_entity
# ---------------------------------------------------------------------------


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
# Tool definitions for Anthropic API
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "query_items",
        "description": (
            "Search and filter the user's TikTok media events. "
            "Supports text search, hashtag filtering, creator filtering, "
            "and classification-based filters. Returns matching items with metadata."
        ),
        "input_schema": {
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
    },
    {
        "name": "classify",
        "description": (
            "Classify a specific media event into ontology categories "
            "(affect, topic, genre, communicative intent, etc.). "
            "Results are cached — subsequent calls return the cache instantly."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "media_event_id": {
                    "type": "string",
                    "description": "UUID of the media event to classify.",
                },
            },
            "required": ["media_event_id"],
        },
    },
    {
        "name": "analyze_visual",
        "description": (
            "Analyze the thumbnail/image of a media event using AI vision. "
            "Returns a description of visual content, detected objects, "
            "OCR text, and relevant web sources from Google Search grounding."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "media_event_id": {
                    "type": "string",
                    "description": "UUID of the media event to analyze visually.",
                },
            },
            "required": ["media_event_id"],
        },
    },
    {
        "name": "resolve_entity",
        "description": (
            "Resolve a named entity (place, book, movie, TV show, song) "
            "mentioned in a media event. Returns structured metadata from "
            "Google Maps, Google Books, TMDB, or Spotify. "
            "Results are cached on the media event."
        ),
        "input_schema": {
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
    },
]
