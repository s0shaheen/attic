"""Tests for agent tool functions (query_items, classify, analyze_visual, resolve_entity).

Each tool returns AgentToolResult and never raises. Tests cover:
- Success paths
- Cache hit/miss behavior
- Error handling (event not found, API failures, DB errors)
- Edge cases (empty results, limit capping)
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from app.services.agent_tools import (
    MAX_QUERY_RESULTS,
    AgentToolResult,
    analyze_visual,
    classify,
    get_stats,
    query_items,
    resolve_entity,
    search_similar,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_SENTINEL = object()


def _make_media_event(
    *,
    id: UUID | None = None,
    user_id: UUID | None = None,
    caption_text: str | None = "A funny cooking video",
    subtitle_text: str | None = "Today we're making pasta",
    full_text: str | None = "A funny cooking video Today we're making pasta",
    hashtags: list[str] | None = _SENTINEL,
    creator_username: str | None = "chef123",
    media_type: str = "video",
    interaction_type: str | None = "liked",
    interaction_at: datetime | None | object = _SENTINEL,
    thumbnail_url: str | None = "https://example.com/thumb.jpg",
    music_name: str | None = "Original Sound",
    play_count: int | None = 1000,
    like_count: int | None = 500,
    video_duration_seconds: int | None = 30,
    cached_classifications: dict | None = None,
    cached_entities: list | None = None,
) -> MagicMock:
    """Build a mock MediaEvent object with sensible defaults."""
    event = MagicMock()
    event.id = id or uuid4()
    event.user_id = user_id or uuid4()
    event.caption_text = caption_text
    event.subtitle_text = subtitle_text
    event.full_text = full_text
    event.hashtags = ["cooking", "food"] if hashtags is _SENTINEL else hashtags
    event.creator_username = creator_username
    event.media_type = media_type
    event.interaction_type = interaction_type
    event.interaction_at = (
        datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)
        if interaction_at is _SENTINEL
        else interaction_at
    )
    event.thumbnail_url = thumbnail_url
    event.music_name = music_name
    event.play_count = play_count
    event.like_count = like_count
    event.video_duration_seconds = video_duration_seconds
    event.cached_classifications = cached_classifications
    event.cached_entities = cached_entities
    return event


def _make_db_session(
    *, scalar_one_or_none=_SENTINEL, scalars_all=_SENTINEL, scalar=_SENTINEL
) -> AsyncMock:
    """Build a mock AsyncSession.

    Args:
        scalar_one_or_none: Return value for result.scalar_one_or_none()
        scalars_all: Return value for result.scalars().all()
        scalar: Return value for result.scalar() (used by count queries)
    """
    db = AsyncMock()

    if scalars_all is not _SENTINEL:
        # query_items calls execute twice: once for count, once for results.
        # First call (count) -> result.scalar()
        # Second call (items) -> result.scalars().all()
        count_result = MagicMock()
        count_result.scalar.return_value = scalar if scalar is not _SENTINEL else 0

        items_result = MagicMock()
        items_scalars = MagicMock()
        items_scalars.all.return_value = scalars_all
        items_result.scalars.return_value = items_scalars

        db.execute = AsyncMock(side_effect=[count_result, items_result])
    elif scalar_one_or_none is not _SENTINEL:
        result = MagicMock()
        result.scalar_one_or_none.return_value = scalar_one_or_none
        db.execute = AsyncMock(return_value=result)
    else:
        db.execute = AsyncMock(return_value=MagicMock())

    db.flush = AsyncMock()
    return db


def _make_settings() -> MagicMock:
    """Build a mock Settings object with test API keys."""
    settings = MagicMock()
    settings.gemini_api_key = "test-gemini-key"
    settings.gemini_model = "gemini-2.0-flash"
    settings.openai_api_key = "test-openai-key"
    settings.google_maps_api_key = "test-maps-key"
    settings.google_books_api_key = "test-books-key"
    settings.tmdb_api_key = "test-tmdb-key"
    settings.spotify_client_id = "test-spotify-id"
    settings.spotify_client_secret = "test-spotify-secret"
    return settings


# ---------------------------------------------------------------------------
# Tool: query_items
# ---------------------------------------------------------------------------


class TestQueryItems:
    async def test_query_items_no_filters_returns_items(self):
        """query_items with no filters returns all user's items."""
        user_id = uuid4()
        events = [_make_media_event(user_id=user_id) for _ in range(3)]
        db = _make_db_session(scalars_all=events, scalar=3)

        result = await query_items(db, user_id)

        assert result.success is True
        assert len(result.data["items"]) == 3
        assert result.data["total"] == 3
        assert result.data["limit"] == 20  # default limit
        assert result.data["offset"] == 0

    async def test_query_items_text_search_filter(self):
        """query_items with search_text filters by caption/subtitle/full_text."""
        user_id = uuid4()
        event = _make_media_event(user_id=user_id, caption_text="pasta recipe")
        db = _make_db_session(scalars_all=[event], scalar=1)

        result = await query_items(db, user_id, search_text="pasta")

        assert result.success is True
        assert len(result.data["items"]) == 1
        assert result.data["items"][0]["caption"] == "pasta recipe"

    async def test_query_items_limit_capped_at_max(self):
        """query_items caps limit at MAX_QUERY_RESULTS (50)."""
        user_id = uuid4()
        db = _make_db_session(scalars_all=[], scalar=0)

        result = await query_items(db, user_id, limit=100)

        assert result.success is True
        assert result.data["limit"] == MAX_QUERY_RESULTS

    async def test_query_items_limit_at_exact_max(self):
        """query_items accepts exactly MAX_QUERY_RESULTS."""
        user_id = uuid4()
        db = _make_db_session(scalars_all=[], scalar=0)

        result = await query_items(db, user_id, limit=50)

        assert result.success is True
        assert result.data["limit"] == 50

    async def test_query_items_limit_below_max_kept(self):
        """query_items keeps limit below MAX_QUERY_RESULTS."""
        user_id = uuid4()
        db = _make_db_session(scalars_all=[], scalar=0)

        result = await query_items(db, user_id, limit=10)

        assert result.success is True
        assert result.data["limit"] == 10

    async def test_query_items_empty_results(self):
        """query_items with no matching items returns empty list."""
        user_id = uuid4()
        db = _make_db_session(scalars_all=[], scalar=0)

        result = await query_items(db, user_id, search_text="nonexistent")

        assert result.success is True
        assert result.data["items"] == []
        assert result.data["total"] == 0

    async def test_query_items_db_error_returns_error_result(self):
        """query_items returns error result when DB raises an exception."""
        user_id = uuid4()
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=Exception("connection lost"))

        result = await query_items(db, user_id)

        assert result.success is False
        assert "Database query failed" in result.error

    async def test_query_items_serializes_item_fields(self):
        """query_items serializes all expected fields from MediaEvent."""
        user_id = uuid4()
        event_id = uuid4()
        interaction_time = datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)
        event = _make_media_event(
            id=event_id,
            user_id=user_id,
            caption_text="test caption",
            creator_username="testuser",
            hashtags=["tag1", "tag2"],
            media_type="video",
            interaction_type="liked",
            interaction_at=interaction_time,
            thumbnail_url="https://example.com/thumb.jpg",
            music_name="Song Name",
            play_count=100,
            like_count=50,
            cached_classifications={"topic": {"label": "food"}},
            cached_entities=[{"entity_type": "place", "name": "NYC"}],
        )
        db = _make_db_session(scalars_all=[event], scalar=1)

        result = await query_items(db, user_id)

        item = result.data["items"][0]
        assert item["id"] == str(event_id)
        assert item["caption"] == "test caption"
        assert item["creator"] == "testuser"
        assert item["hashtags"] == ["tag1", "tag2"]
        assert item["media_type"] == "video"
        assert item["interaction_type"] == "liked"
        assert item["interaction_at"] == interaction_time.isoformat()
        assert item["thumbnail_url"] == "https://example.com/thumb.jpg"
        assert item["music_name"] == "Song Name"
        assert item["play_count"] == 100
        assert item["like_count"] == 50
        assert item["cached_classifications"] == {"topic": {"label": "food"}}
        assert item["cached_entities"] == [{"entity_type": "place", "name": "NYC"}]

    async def test_query_items_null_interaction_at(self):
        """query_items handles null interaction_at gracefully."""
        user_id = uuid4()
        event = _make_media_event(user_id=user_id, interaction_at=None)
        db = _make_db_session(scalars_all=[event], scalar=1)

        result = await query_items(db, user_id)

        assert result.success is True
        assert result.data["items"][0]["interaction_at"] is None

    async def test_query_items_null_hashtags(self):
        """query_items returns empty list for null hashtags."""
        user_id = uuid4()
        event = _make_media_event(user_id=user_id)
        event.hashtags = None
        db = _make_db_session(scalars_all=[event], scalar=1)

        result = await query_items(db, user_id)

        assert result.success is True
        assert result.data["items"][0]["hashtags"] == []

    async def test_query_items_with_offset(self):
        """query_items passes offset to the query."""
        user_id = uuid4()
        db = _make_db_session(scalars_all=[], scalar=10)

        result = await query_items(db, user_id, offset=5)

        assert result.success is True
        assert result.data["offset"] == 5

    async def test_query_items_null_count_returns_zero_total(self):
        """query_items treats null count as zero total."""
        user_id = uuid4()
        db = _make_db_session(scalars_all=[], scalar=None)

        result = await query_items(db, user_id)

        assert result.success is True
        assert result.data["total"] == 0


# ---------------------------------------------------------------------------
# Tool: classify
# ---------------------------------------------------------------------------


class TestClassify:
    async def test_classify_cache_hit_returns_cached_data(self):
        """classify returns cached_classifications when present on event."""
        user_id = uuid4()
        event_id = uuid4()
        cached = {
            "tier1": {"affect": "funny", "topic": "food"},
            "tier2": {},
            "confidence": {"affect": 0.9, "topic": 0.8},
        }
        event = _make_media_event(id=event_id, user_id=user_id, cached_classifications=cached)
        db = _make_db_session(scalar_one_or_none=event)

        result = await classify(db, _make_settings(), event_id, user_id)

        assert result.success is True
        assert result.data == cached

    async def test_classify_cache_miss_calls_gemini_and_writes_db(self):
        """classify calls gemini, validates, and writes result to DB on cache miss."""
        user_id = uuid4()
        event_id = uuid4()
        event = _make_media_event(id=event_id, user_id=user_id, cached_classifications=None)
        db = _make_db_session(scalar_one_or_none=event)

        raw_classification = {
            "affect": {"label": "funny", "micro_labels": ["hilarious"], "confidence": 0.9},
            "topic": {"label": "food", "confidence": 0.8},
        }

        gemini_result = MagicMock()
        gemini_result.success = True
        gemini_result.raw_classification = raw_classification
        gemini_result.summary = "A funny cooking tutorial"
        gemini_result.entities = [{"name": "Pasta", "type": "recipe", "relevance": "primary"}]
        gemini_result.embedding_text = "Funny cooking video about pasta"

        with patch(
            "app.services.agent_tools.gemini_classify", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = gemini_result

            result = await classify(db, _make_settings(), event_id, user_id)

        assert result.success is True
        assert "tier1" in result.data
        assert "tier2" in result.data
        assert "confidence" in result.data
        assert result.data["source"] == "agent_chat"
        assert result.data["summary"] == "A funny cooking tutorial"
        assert result.data["entities"][0]["name"] == "Pasta"
        assert result.data["embedding_text"] == "Funny cooking video about pasta"

        # Verify gemini was called with correct args (including enriched context)
        mock_gemini.assert_called_once_with(
            api_key="test-gemini-key",
            caption=event.caption_text,
            subtitle=event.subtitle_text,
            hashtags=event.hashtags,
            creator_username=event.creator_username,
            music_name=event.music_name,
            duration_seconds=event.video_duration_seconds,
            thumbnail_url=event.thumbnail_url,
            model="gemini-2.0-flash",
        )

        # Verify DB was updated (event.cached_classifications set + flush)
        assert event.cached_classifications is not None
        assert event.cached_classifications["tier1"]["affect"] == "funny"
        db.flush.assert_awaited_once()

    async def test_classify_event_not_found_returns_error(self):
        """classify returns error when media event not found."""
        user_id = uuid4()
        event_id = uuid4()
        db = _make_db_session(scalar_one_or_none=None)

        result = await classify(db, _make_settings(), event_id, user_id)

        assert result.success is False
        assert "not found" in result.error.lower()

    async def test_classify_gemini_error_returns_error(self):
        """classify returns error when gemini_classify fails."""
        user_id = uuid4()
        event_id = uuid4()
        event = _make_media_event(id=event_id, user_id=user_id, cached_classifications=None)
        db = _make_db_session(scalar_one_or_none=event)

        gemini_result = MagicMock()
        gemini_result.success = False
        gemini_result.error = "Gemini API error: 500"

        with patch(
            "app.services.agent_tools.gemini_classify", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = gemini_result

            result = await classify(db, _make_settings(), event_id, user_id)

        assert result.success is False
        assert "500" in result.error

    async def test_classify_exception_returns_error_result(self):
        """classify returns error result when an unexpected exception occurs."""
        user_id = uuid4()
        event_id = uuid4()
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=Exception("unexpected DB error"))

        result = await classify(db, _make_settings(), event_id, user_id)

        assert result.success is False
        assert "Classification failed" in result.error

    async def test_classify_validates_through_ontology(self):
        """classify passes raw classification through validate_classification."""
        user_id = uuid4()
        event_id = uuid4()
        event = _make_media_event(id=event_id, user_id=user_id, cached_classifications=None)
        db = _make_db_session(scalar_one_or_none=event)

        raw_classification = {
            "affect": {"label": "funny", "confidence": 0.9},
            "topic": {"label": "food", "confidence": 0.85},
            "genre": {"label": "recipe", "confidence": 0.7},
        }

        gemini_result = MagicMock()
        gemini_result.success = True
        gemini_result.raw_classification = raw_classification

        with (
            patch(
                "app.services.agent_tools.gemini_classify", new_callable=AsyncMock
            ) as mock_gemini,
            patch("app.services.agent_tools.validate_classification") as mock_validate,
        ):
            mock_gemini.return_value = gemini_result
            mock_validate.return_value = MagicMock(
                tier1={"affect": "funny", "topic": "food", "genre": "recipe"},
                tier2={},
                confidence={"affect": 0.9, "topic": 0.85, "genre": 0.7},
            )

            result = await classify(db, _make_settings(), event_id, user_id)

        mock_validate.assert_called_once_with(raw_classification)
        assert result.success is True

    async def test_classify_does_not_call_gemini_on_cache_hit(self):
        """classify does NOT call gemini_classify when cache exists."""
        user_id = uuid4()
        event_id = uuid4()
        cached = {"tier1": {"affect": "funny"}, "tier2": {}, "confidence": {"affect": 0.9}}
        event = _make_media_event(id=event_id, user_id=user_id, cached_classifications=cached)
        db = _make_db_session(scalar_one_or_none=event)

        with patch(
            "app.services.agent_tools.gemini_classify", new_callable=AsyncMock
        ) as mock_gemini:
            result = await classify(db, _make_settings(), event_id, user_id)

        mock_gemini.assert_not_called()
        assert result.success is True


# ---------------------------------------------------------------------------
# Tool: analyze_visual
# ---------------------------------------------------------------------------


class TestAnalyzeVisual:
    async def test_analyze_visual_success(self):
        """analyze_visual returns visual analysis data on success."""
        user_id = uuid4()
        event_id = uuid4()
        event = _make_media_event(
            id=event_id,
            user_id=user_id,
            thumbnail_url="https://example.com/thumb.jpg",
        )
        db = _make_db_session(scalar_one_or_none=event)

        visual_result = MagicMock()
        visual_result.success = True
        visual_result.description = "A person cooking pasta"
        visual_result.objects = ["pan", "pasta", "kitchen"]
        visual_result.text_detected = "Recipe: Easy Pasta"
        visual_result.grounding_sources = [{"uri": "https://example.com", "title": "Example"}]

        with patch(
            "app.services.agent_tools.gemini_analyze", new_callable=AsyncMock
        ) as mock_analyze:
            mock_analyze.return_value = visual_result

            result = await analyze_visual(db, _make_settings(), event_id, user_id)

        assert result.success is True
        assert result.data["description"] == "A person cooking pasta"
        assert result.data["objects"] == ["pan", "pasta", "kitchen"]
        assert result.data["text_detected"] == "Recipe: Easy Pasta"
        assert len(result.data["grounding_sources"]) == 1

        from app.services.gemini import VisionFocus

        mock_analyze.assert_called_once_with(
            api_key="test-gemini-key",
            image_url="https://example.com/thumb.jpg",
            caption=event.caption_text,
            focus=VisionFocus.GENERAL,
        )

    async def test_analyze_visual_no_thumbnail_returns_error(self):
        """analyze_visual returns error when event has no thumbnail_url."""
        user_id = uuid4()
        event_id = uuid4()
        event = _make_media_event(id=event_id, user_id=user_id, thumbnail_url=None)
        db = _make_db_session(scalar_one_or_none=event)

        result = await analyze_visual(db, _make_settings(), event_id, user_id)

        assert result.success is False
        assert "thumbnail" in result.error.lower()

    async def test_analyze_visual_empty_thumbnail_returns_error(self):
        """analyze_visual returns error when event has empty thumbnail_url."""
        user_id = uuid4()
        event_id = uuid4()
        event = _make_media_event(id=event_id, user_id=user_id, thumbnail_url="")
        db = _make_db_session(scalar_one_or_none=event)

        result = await analyze_visual(db, _make_settings(), event_id, user_id)

        assert result.success is False
        assert "thumbnail" in result.error.lower()

    async def test_analyze_visual_event_not_found_returns_error(self):
        """analyze_visual returns error when media event not found."""
        user_id = uuid4()
        event_id = uuid4()
        db = _make_db_session(scalar_one_or_none=None)

        result = await analyze_visual(db, _make_settings(), event_id, user_id)

        assert result.success is False
        assert "not found" in result.error.lower()

    async def test_analyze_visual_gemini_error_returns_error(self):
        """analyze_visual returns error when gemini_analyze fails."""
        user_id = uuid4()
        event_id = uuid4()
        event = _make_media_event(
            id=event_id,
            user_id=user_id,
            thumbnail_url="https://example.com/thumb.jpg",
        )
        db = _make_db_session(scalar_one_or_none=event)

        visual_result = MagicMock()
        visual_result.success = False
        visual_result.error = "Gemini visual analysis timed out"

        with patch(
            "app.services.agent_tools.gemini_analyze", new_callable=AsyncMock
        ) as mock_analyze:
            mock_analyze.return_value = visual_result

            result = await analyze_visual(db, _make_settings(), event_id, user_id)

        assert result.success is False
        assert "timed out" in result.error

    async def test_analyze_visual_exception_returns_error_result(self):
        """analyze_visual returns error result when an unexpected exception occurs."""
        user_id = uuid4()
        event_id = uuid4()
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=Exception("DB connection lost"))

        result = await analyze_visual(db, _make_settings(), event_id, user_id)

        assert result.success is False
        assert "Visual analysis failed" in result.error

    async def test_analyze_visual_passes_focus_to_gemini(self):
        """analyze_visual passes focus mode through to gemini_analyze."""
        from app.services.gemini import VisionFocus

        user_id = uuid4()
        event_id = uuid4()
        event = _make_media_event(
            id=event_id,
            user_id=user_id,
            thumbnail_url="https://example.com/thumb.jpg",
        )
        db = _make_db_session(scalar_one_or_none=event)

        visual_result = MagicMock()
        visual_result.success = True
        visual_result.description = "A book cover"
        visual_result.objects = ["book"]
        visual_result.text_detected = "Atomic Habits"
        visual_result.grounding_sources = []

        with patch(
            "app.services.agent_tools.gemini_analyze", new_callable=AsyncMock
        ) as mock_analyze:
            mock_analyze.return_value = visual_result

            result = await analyze_visual(db, _make_settings(), event_id, user_id, focus="books")

        assert result.success is True
        mock_analyze.assert_called_once_with(
            api_key="test-gemini-key",
            image_url="https://example.com/thumb.jpg",
            caption=event.caption_text,
            focus=VisionFocus.BOOKS,
        )

    async def test_analyze_visual_none_focus_defaults_to_general(self):
        """analyze_visual with focus=None passes VisionFocus.GENERAL to gemini."""
        from app.services.gemini import VisionFocus

        user_id = uuid4()
        event_id = uuid4()
        event = _make_media_event(
            id=event_id,
            user_id=user_id,
            thumbnail_url="https://example.com/thumb.jpg",
        )
        db = _make_db_session(scalar_one_or_none=event)

        visual_result = MagicMock()
        visual_result.success = True
        visual_result.description = "A cooking scene"
        visual_result.objects = ["pan"]
        visual_result.text_detected = None
        visual_result.grounding_sources = []

        with patch(
            "app.services.agent_tools.gemini_analyze", new_callable=AsyncMock
        ) as mock_analyze:
            mock_analyze.return_value = visual_result

            await analyze_visual(db, _make_settings(), event_id, user_id, focus=None)

        mock_analyze.assert_called_once()
        assert mock_analyze.call_args.kwargs["focus"] == VisionFocus.GENERAL

    async def test_analyze_visual_invalid_focus_returns_error(self):
        """analyze_visual returns error for invalid focus mode."""
        user_id = uuid4()
        event_id = uuid4()

        result = await analyze_visual(
            AsyncMock(), _make_settings(), event_id, user_id, focus="invalid_mode"
        )

        assert result.success is False
        assert "Invalid focus mode" in result.error
        assert "invalid_mode" in result.error
        assert "general" in result.error  # Lists valid values


# ---------------------------------------------------------------------------
# Tool: resolve_entity
# ---------------------------------------------------------------------------


class TestResolveEntity:
    async def test_resolve_entity_success_and_cache_write(self):
        """resolve_entity resolves via external API and writes to cached_entities."""
        user_id = uuid4()
        event_id = uuid4()
        event = _make_media_event(id=event_id, user_id=user_id, cached_entities=None)
        db = _make_db_session(scalar_one_or_none=event)

        resolved = MagicMock()
        resolved.success = True
        resolved.entity = MagicMock()
        resolved.entity.entity_type = "book"
        resolved.entity.surface = "Atomic Habits"
        resolved.entity.name = "Atomic Habits"
        resolved.entity.metadata = {"authors": ["James Clear"]}

        with patch(
            "app.services.agent_tools._resolve_entity", new_callable=AsyncMock
        ) as mock_resolve:
            mock_resolve.return_value = resolved

            result = await resolve_entity(
                db, _make_settings(), event_id, user_id, "book", "Atomic Habits"
            )

        assert result.success is True
        assert result.data["entity_type"] == "book"
        assert result.data["name"] == "Atomic Habits"
        assert result.data["surface"] == "Atomic Habits"
        assert result.data["metadata"] == {"authors": ["James Clear"]}

        # Verify cached_entities was updated
        assert event.cached_entities is not None
        assert len(event.cached_entities) == 1
        assert event.cached_entities[0]["name"] == "Atomic Habits"
        db.flush.assert_awaited_once()

    async def test_resolve_entity_appends_to_existing_cache(self):
        """resolve_entity appends to existing cached_entities, not replaces."""
        user_id = uuid4()
        event_id = uuid4()
        existing_entity = {
            "entity_type": "place",
            "surface": "NYC",
            "name": "New York City",
            "metadata": {},
        }
        event = _make_media_event(id=event_id, user_id=user_id, cached_entities=[existing_entity])
        db = _make_db_session(scalar_one_or_none=event)

        resolved = MagicMock()
        resolved.success = True
        resolved.entity = MagicMock()
        resolved.entity.entity_type = "book"
        resolved.entity.surface = "Atomic Habits"
        resolved.entity.name = "Atomic Habits"
        resolved.entity.metadata = {}

        with patch(
            "app.services.agent_tools._resolve_entity", new_callable=AsyncMock
        ) as mock_resolve:
            mock_resolve.return_value = resolved

            result = await resolve_entity(
                db, _make_settings(), event_id, user_id, "book", "Atomic Habits"
            )

        assert result.success is True
        assert len(event.cached_entities) == 2
        assert event.cached_entities[0]["name"] == "New York City"
        assert event.cached_entities[1]["name"] == "Atomic Habits"

    async def test_resolve_entity_cache_hit_returns_cached_entity(self):
        """resolve_entity returns cached entity when matching surface+type found."""
        user_id = uuid4()
        event_id = uuid4()
        cached_entity = {
            "entity_type": "book",
            "surface": "Atomic Habits",
            "name": "Atomic Habits",
            "metadata": {"authors": ["James Clear"]},
        }
        event = _make_media_event(id=event_id, user_id=user_id, cached_entities=[cached_entity])
        db = _make_db_session(scalar_one_or_none=event)

        with patch(
            "app.services.agent_tools._resolve_entity", new_callable=AsyncMock
        ) as mock_resolve:
            result = await resolve_entity(
                db, _make_settings(), event_id, user_id, "book", "Atomic Habits"
            )

        # External API should NOT be called
        mock_resolve.assert_not_called()
        assert result.success is True
        assert result.data["name"] == "Atomic Habits"

    async def test_resolve_entity_cache_hit_case_insensitive(self):
        """resolve_entity cache lookup is case insensitive on surface text."""
        user_id = uuid4()
        event_id = uuid4()
        cached_entity = {
            "entity_type": "book",
            "surface": "atomic habits",
            "name": "Atomic Habits",
            "metadata": {},
        }
        event = _make_media_event(id=event_id, user_id=user_id, cached_entities=[cached_entity])
        db = _make_db_session(scalar_one_or_none=event)

        with patch(
            "app.services.agent_tools._resolve_entity", new_callable=AsyncMock
        ) as mock_resolve:
            result = await resolve_entity(
                db, _make_settings(), event_id, user_id, "book", "ATOMIC HABITS"
            )

        mock_resolve.assert_not_called()
        assert result.success is True

    async def test_resolve_entity_no_cache_hit_when_type_differs(self):
        """resolve_entity does not cache-hit when entity_type differs."""
        user_id = uuid4()
        event_id = uuid4()
        cached_entity = {
            "entity_type": "place",
            "surface": "Atomic Habits",
            "name": "Atomic Habits Cafe",
            "metadata": {},
        }
        event = _make_media_event(id=event_id, user_id=user_id, cached_entities=[cached_entity])
        db = _make_db_session(scalar_one_or_none=event)

        resolved = MagicMock()
        resolved.success = True
        resolved.entity = MagicMock()
        resolved.entity.entity_type = "book"
        resolved.entity.surface = "Atomic Habits"
        resolved.entity.name = "Atomic Habits"
        resolved.entity.metadata = {}

        with patch(
            "app.services.agent_tools._resolve_entity", new_callable=AsyncMock
        ) as mock_resolve:
            mock_resolve.return_value = resolved

            result = await resolve_entity(
                db, _make_settings(), event_id, user_id, "book", "Atomic Habits"
            )

        # External API SHOULD be called because entity_type differs
        mock_resolve.assert_called_once()
        assert result.success is True

    async def test_resolve_entity_event_not_found_returns_error(self):
        """resolve_entity returns error when media event not found."""
        user_id = uuid4()
        event_id = uuid4()
        db = _make_db_session(scalar_one_or_none=None)

        result = await resolve_entity(
            db, _make_settings(), event_id, user_id, "book", "Atomic Habits"
        )

        assert result.success is False
        assert "not found" in result.error.lower()

    async def test_resolve_entity_resolver_error_returns_error(self):
        """resolve_entity returns error when external resolver fails."""
        user_id = uuid4()
        event_id = uuid4()
        event = _make_media_event(id=event_id, user_id=user_id, cached_entities=None)
        db = _make_db_session(scalar_one_or_none=event)

        resolved = MagicMock()
        resolved.success = False
        resolved.error = "TMDB request timed out"

        with patch(
            "app.services.agent_tools._resolve_entity", new_callable=AsyncMock
        ) as mock_resolve:
            mock_resolve.return_value = resolved

            result = await resolve_entity(
                db, _make_settings(), event_id, user_id, "movie", "Inception"
            )

        assert result.success is False
        assert "timed out" in result.error

    async def test_resolve_entity_exception_returns_error_result(self):
        """resolve_entity returns error result when an unexpected exception occurs."""
        user_id = uuid4()
        event_id = uuid4()
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=Exception("DB timeout"))

        result = await resolve_entity(
            db, _make_settings(), event_id, user_id, "book", "Atomic Habits"
        )

        assert result.success is False
        assert "Entity resolution failed" in result.error

    async def test_resolve_entity_passes_correct_api_keys(self):
        """resolve_entity passes the correct API keys from settings to the resolver."""
        user_id = uuid4()
        event_id = uuid4()
        event = _make_media_event(id=event_id, user_id=user_id, cached_entities=None)
        db = _make_db_session(scalar_one_or_none=event)
        settings = _make_settings()

        resolved = MagicMock()
        resolved.success = True
        resolved.entity = MagicMock()
        resolved.entity.entity_type = "place"
        resolved.entity.surface = "Shake Shack"
        resolved.entity.name = "Shake Shack"
        resolved.entity.metadata = {}

        with patch(
            "app.services.agent_tools._resolve_entity", new_callable=AsyncMock
        ) as mock_resolve:
            mock_resolve.return_value = resolved

            await resolve_entity(db, settings, event_id, user_id, "place", "Shake Shack")

        mock_resolve.assert_called_once_with(
            entity_type="place",
            query="Shake Shack",
            google_maps_api_key="test-maps-key",
            google_books_api_key="test-books-key",
            tmdb_api_key="test-tmdb-key",
            spotify_client_id="test-spotify-id",
            spotify_client_secret="test-spotify-secret",
        )

    async def test_resolve_entity_does_not_flush_on_resolver_error(self):
        """resolve_entity does not flush DB when resolver fails."""
        user_id = uuid4()
        event_id = uuid4()
        event = _make_media_event(id=event_id, user_id=user_id, cached_entities=None)
        db = _make_db_session(scalar_one_or_none=event)

        resolved = MagicMock()
        resolved.success = False
        resolved.error = "No places found"

        with patch(
            "app.services.agent_tools._resolve_entity", new_callable=AsyncMock
        ) as mock_resolve:
            mock_resolve.return_value = resolved

            await resolve_entity(db, _make_settings(), event_id, user_id, "place", "nonexistent")

        db.flush.assert_not_awaited()

    async def test_resolve_entity_skips_non_dict_entries_in_cache(self):
        """resolve_entity skips non-dict entries in cached_entities during cache check."""
        user_id = uuid4()
        event_id = uuid4()
        # Simulate corrupted cache data
        event = _make_media_event(
            id=event_id,
            user_id=user_id,
            cached_entities=["not_a_dict", 42, None],
        )
        db = _make_db_session(scalar_one_or_none=event)

        resolved = MagicMock()
        resolved.success = True
        resolved.entity = MagicMock()
        resolved.entity.entity_type = "book"
        resolved.entity.surface = "Test"
        resolved.entity.name = "Test Book"
        resolved.entity.metadata = {}

        with patch(
            "app.services.agent_tools._resolve_entity", new_callable=AsyncMock
        ) as mock_resolve:
            mock_resolve.return_value = resolved

            result = await resolve_entity(db, _make_settings(), event_id, user_id, "book", "Test")

        # Should proceed to external API since no valid cache entry matched
        mock_resolve.assert_called_once()
        assert result.success is True


# ---------------------------------------------------------------------------
# AgentToolResult dataclass
# ---------------------------------------------------------------------------


class TestAgentToolResult:
    def test_default_fields(self):
        """AgentToolResult has correct defaults."""
        result = AgentToolResult(success=True)
        assert result.success is True
        assert result.data is None
        assert result.error is None
        assert result.partial_data is None

    def test_success_with_data(self):
        result = AgentToolResult(success=True, data={"items": [1, 2, 3]})
        assert result.data == {"items": [1, 2, 3]}

    def test_failure_with_error(self):
        result = AgentToolResult(success=False, error="Something failed")
        assert result.error == "Something failed"

    def test_failure_with_partial_data(self):
        result = AgentToolResult(
            success=False,
            error="Partial failure",
            partial_data={"items": [1]},
        )
        assert result.partial_data == {"items": [1]}


# ---------------------------------------------------------------------------
# Tool: search_similar
# ---------------------------------------------------------------------------


def _make_search_db(*, embedded_count: int = 10, search_rows: list | None = None) -> AsyncMock:
    """Build a mock AsyncSession for search_similar tests.

    search_similar calls execute three times:
    1. Count query (embedded items) -> scalar()
    2. Raw SQL similarity search -> mappings().all()
    """
    db = AsyncMock()

    count_result = MagicMock()
    count_result.scalar.return_value = embedded_count

    search_result = MagicMock()
    search_mappings = MagicMock()
    search_mappings.all.return_value = search_rows or []
    search_result.mappings.return_value = search_mappings

    db.execute = AsyncMock(side_effect=[count_result, search_result])
    return db


def _make_search_row(
    *,
    id: UUID | None = None,
    distance: float = 0.2,
    caption_text: str = "A test caption",
    creator_username: str = "testuser",
) -> dict:
    """Build a mock row dict for search_similar results."""
    return {
        "id": id or uuid4(),
        "caption_text": caption_text,
        "creator_username": creator_username,
        "hashtags": ["test"],
        "media_type": "video",
        "interaction_type": "liked",
        "interaction_at": datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC),
        "thumbnail_url": "https://example.com/thumb.jpg",
        "canonical_url": "https://www.tiktok.com/@user/video/123",
        "music_name": "Original Sound",
        "play_count": 1000,
        "like_count": 500,
        "cached_classifications": None,
        "distance": distance,
    }


class TestSearchSimilar:
    async def test_search_similar_success_returns_items(self):
        """search_similar returns items with similarity scores."""
        user_id = uuid4()
        rows = [
            _make_search_row(distance=0.15, caption_text="relaxing nature"),
            _make_search_row(distance=0.25, caption_text="calm ocean waves"),
        ]
        db = _make_search_db(embedded_count=100, search_rows=rows)

        mock_embedding = [0.1] * 1536
        with patch("app.services.agent_tools._embed_query", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = mock_embedding
            result = await search_similar(db, _make_settings(), user_id, query_text="relaxing")

        assert result.success is True
        assert len(result.data["items"]) == 2
        assert result.data["total_embedded"] == 100
        assert result.data["query"] == "relaxing"
        # Similarity = 1 - distance
        assert result.data["items"][0]["similarity"] == round(1.0 - 0.15, 4)
        assert result.data["items"][0]["caption"] == "relaxing nature"

    async def test_search_similar_empty_results(self):
        """search_similar returns empty list when no similar items found."""
        user_id = uuid4()
        db = _make_search_db(embedded_count=100, search_rows=[])

        with patch("app.services.agent_tools._embed_query", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 1536
            result = await search_similar(db, _make_settings(), user_id, query_text="xyz")

        assert result.success is True
        assert result.data["items"] == []
        assert result.data["total_embedded"] == 100

    async def test_search_similar_no_embeddings_returns_note(self):
        """search_similar returns informative note when no embeddings exist."""
        user_id = uuid4()
        # Only the count query is executed when embedded_count == 0
        db = AsyncMock()
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        db.execute = AsyncMock(return_value=count_result)

        result = await search_similar(db, _make_settings(), user_id, query_text="test")

        assert result.success is True
        assert result.data["total_embedded"] == 0
        assert "still being processed" in result.data["note"]
        assert result.data["items"] == []

    async def test_search_similar_openai_timeout_returns_error(self):
        """search_similar returns error when OpenAI embedding API fails."""
        user_id = uuid4()
        db = _make_search_db(embedded_count=100)

        with patch("app.services.agent_tools._embed_query", new_callable=AsyncMock) as mock_embed:
            mock_embed.side_effect = Exception("Connection timeout")
            result = await search_similar(db, _make_settings(), user_id, query_text="test")

        assert result.success is False
        assert "search embedding" in result.error.lower()


# ---------------------------------------------------------------------------
# Tool: get_stats
# ---------------------------------------------------------------------------


def _make_stats_db(*, row: dict | None = None, rows: list | None = None) -> AsyncMock:
    """Build a mock AsyncSession for get_stats tests.

    Args:
        row: Single row return (for queries using .one())
        rows: Multiple rows return (for queries using .all())
    """
    db = AsyncMock()

    if row is not None:
        result = MagicMock()
        mapping = MagicMock()
        mapping.one.return_value = row
        result.mappings.return_value = mapping
        db.execute = AsyncMock(return_value=result)
    elif rows is not None:
        result = MagicMock()
        mapping = MagicMock()
        mapping.all.return_value = rows
        result.mappings.return_value = mapping
        db.execute = AsyncMock(return_value=result)

    return db


class TestGetStats:
    async def test_get_stats_overview(self):
        """get_stats overview returns counts, date range, and media types."""
        user_id = uuid4()
        row = {
            "total_items": 847,
            "earliest": datetime(2024, 1, 1, tzinfo=UTC),
            "latest": datetime(2025, 6, 15, tzinfo=UTC),
            "video_count": 700,
            "image_count": 100,
            "slideshow_count": 47,
            "unique_creators": 234,
            "embedded_count": 800,
        }
        db = _make_stats_db(row=row)

        result = await get_stats(db, user_id, stat_type="overview")

        assert result.success is True
        assert result.data["total_items"] == 847
        assert result.data["media_types"]["video"] == 700
        assert result.data["unique_creators"] == 234
        assert result.data["embedded_count"] == 800

    async def test_get_stats_top_creators(self):
        """get_stats top_creators returns creators sorted by count."""
        user_id = uuid4()
        rows = [
            {"creator_username": "chef123", "item_count": 45},
            {"creator_username": "dancer456", "item_count": 30},
        ]
        db = _make_stats_db(rows=rows)

        result = await get_stats(db, user_id, stat_type="top_creators")

        assert result.success is True
        assert len(result.data["creators"]) == 2
        assert result.data["creators"][0]["creator"] == "chef123"
        assert result.data["creators"][0]["count"] == 45

    async def test_get_stats_top_hashtags(self):
        """get_stats top_hashtags returns hashtags sorted by frequency."""
        user_id = uuid4()
        rows = [
            {"tag": "cooking", "frequency": 120},
            {"tag": "food", "frequency": 95},
            {"tag": "recipe", "frequency": 60},
        ]
        db = _make_stats_db(rows=rows)

        result = await get_stats(db, user_id, stat_type="top_hashtags")

        assert result.success is True
        assert len(result.data["hashtags"]) == 3
        assert result.data["hashtags"][0]["hashtag"] == "cooking"
        assert result.data["hashtags"][0]["count"] == 120

    async def test_get_stats_interaction_timeline(self):
        """get_stats interaction_timeline returns monthly counts."""
        user_id = uuid4()
        rows = [
            {"month": datetime(2025, 1, 1, tzinfo=UTC), "item_count": 100},
            {"month": datetime(2025, 2, 1, tzinfo=UTC), "item_count": 150},
            {"month": datetime(2025, 3, 1, tzinfo=UTC), "item_count": 120},
        ]
        db = _make_stats_db(rows=rows)

        result = await get_stats(db, user_id, stat_type="interaction_timeline")

        assert result.success is True
        assert len(result.data["timeline"]) == 3
        assert result.data["timeline"][1]["count"] == 150

    async def test_get_stats_classification_breakdown_sparse(self):
        """get_stats classification_breakdown includes coverage context."""
        user_id = uuid4()

        # First call: count query returns total + classified counts
        count_result = MagicMock()
        count_mapping = MagicMock()
        count_mapping.one.return_value = {"total_count": 847, "classified_count": 45}
        count_result.mappings.return_value = count_mapping

        # Second call: single facet query returns all facets in one result set
        facet_rows = [
            {"facet": "topic", "label": "food", "count": 20},
            {"facet": "topic", "label": "fitness", "count": 10},
            {"facet": "affect", "label": "funny", "count": 25},
            {"facet": "genre", "label": "tutorial", "count": 15},
        ]
        facet_result = MagicMock()
        facet_mapping = MagicMock()
        facet_mapping.all.return_value = facet_rows
        facet_result.mappings.return_value = facet_mapping

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[count_result, facet_result])

        result = await get_stats(db, user_id, stat_type="classification_breakdown")

        assert result.success is True
        assert result.data["classified_count"] == 45
        assert result.data["total_count"] == 847
        assert result.data["coverage_pct"] == round((45 / 847) * 100, 1)
        assert len(result.data["distributions"]["topic"]) == 2
        assert result.data["distributions"]["topic"][0]["label"] == "food"

    async def test_get_stats_invalid_stat_type(self):
        """get_stats returns error for unknown stat_type."""
        user_id = uuid4()
        db = AsyncMock()

        result = await get_stats(db, user_id, stat_type="invalid_type")

        assert result.success is False
        assert "Unknown stat_type" in result.error
