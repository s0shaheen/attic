"""Tests for get_stats aggregation extensions (creator_details, field_distribution).

Tests cover:
- creator_details: happy path, empty results, topic enrichment, mixed classification, user isolation
- field_distribution: happy path per field, missing/invalid field, empty results, user isolation
- Schema: new stat_types and field param present in tool definitions
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.services.agent_tools import (
    _AGGREGATE_FIELDS,
    _VALID_STAT_TYPES,
    get_stats,
    get_tool_definitions,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stats_db_multi(*call_results: list[dict] | dict) -> AsyncMock:
    """Build a mock AsyncSession that returns different results for sequential execute() calls.

    Each argument is either:
    - A dict: returned via mappings().one()
    - A list of dicts: returned via mappings().all()
    """
    db = AsyncMock()
    side_effects = []

    for call_result in call_results:
        result = MagicMock()
        mapping = MagicMock()
        if isinstance(call_result, list):
            mapping.all.return_value = call_result
        else:
            mapping.one.return_value = call_result
        result.mappings.return_value = mapping
        side_effects.append(result)

    db.execute = AsyncMock(side_effect=side_effects)
    return db


def _make_stats_db_rows(rows: list[dict]) -> AsyncMock:
    """Build a mock AsyncSession for a single query returning multiple rows."""
    return _make_stats_db_multi(rows)


# ---------------------------------------------------------------------------
# Tests: creator_details
# ---------------------------------------------------------------------------


class TestCreatorDetails:
    async def test_creator_details_happy_path(self):
        """creator_details returns top creators with counts, dates, and topics."""
        user_id = uuid4()
        creator_rows = [
            {
                "creator_username": "chef123",
                "item_count": 45,
                "first_seen": datetime(2024, 3, 1, tzinfo=UTC),
                "last_seen": datetime(2025, 6, 15, tzinfo=UTC),
            },
            {
                "creator_username": "dancer456",
                "item_count": 30,
                "first_seen": datetime(2024, 5, 10, tzinfo=UTC),
                "last_seen": datetime(2025, 5, 1, tzinfo=UTC),
            },
            {
                "creator_username": "gamer789",
                "item_count": 15,
                "first_seen": datetime(2025, 1, 1, tzinfo=UTC),
                "last_seen": datetime(2025, 6, 10, tzinfo=UTC),
            },
        ]
        topic_rows = [
            {"creator_username": "chef123", "topic": "food", "topic_count": 20},
            {"creator_username": "chef123", "topic": "cooking", "topic_count": 15},
            {"creator_username": "chef123", "topic": "lifestyle", "topic_count": 5},
            {"creator_username": "dancer456", "topic": "dance", "topic_count": 18},
            {"creator_username": "dancer456", "topic": "fitness", "topic_count": 8},
        ]
        db = _make_stats_db_multi(creator_rows, topic_rows)

        result = await get_stats(db, user_id, stat_type="creator_details")

        assert result.success is True
        assert len(result.data["creators"]) == 3

        # First creator (highest count)
        chef = result.data["creators"][0]
        assert chef["creator"] == "chef123"
        assert chef["count"] == 45
        assert chef["first_seen"] is not None
        assert chef["last_seen"] is not None
        assert len(chef["top_topics"]) == 3
        assert chef["top_topics"][0]["topic"] == "food"

        # Second creator
        dancer = result.data["creators"][1]
        assert dancer["creator"] == "dancer456"
        assert len(dancer["top_topics"]) == 2

        # Third creator (no topics)
        gamer = result.data["creators"][2]
        assert gamer["creator"] == "gamer789"
        assert gamer["top_topics"] == []

    async def test_creator_details_no_creators(self):
        """creator_details returns helpful note when no creator data exists."""
        user_id = uuid4()
        db = _make_stats_db_rows([])

        result = await get_stats(db, user_id, stat_type="creator_details")

        assert result.success is True
        assert result.data["creators"] == []
        assert "note" in result.data

    async def test_creator_details_user_isolation(self):
        """creator_details passes user_id to both queries for isolation."""
        user_id = uuid4()
        db = _make_stats_db_multi([], [])

        # First call returns empty -> early return, so only 1 execute call
        db = _make_stats_db_rows([])
        await get_stats(db, user_id, stat_type="creator_details")

        # Verify the query was called with user_id
        call_args = db.execute.call_args_list[0]
        params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params", {})
        assert params.get("uid") == str(user_id)

    async def test_creator_details_with_topics(self):
        """creator_details enriches creators with top 3 topics from cached classifications."""
        user_id = uuid4()
        creator_rows = [
            {
                "creator_username": "creator1",
                "item_count": 50,
                "first_seen": datetime(2024, 1, 1, tzinfo=UTC),
                "last_seen": datetime(2025, 6, 1, tzinfo=UTC),
            },
        ]
        # More than 3 topics — should only take top 3
        topic_rows = [
            {"creator_username": "creator1", "topic": "tech", "topic_count": 25},
            {"creator_username": "creator1", "topic": "science", "topic_count": 15},
            {"creator_username": "creator1", "topic": "coding", "topic_count": 8},
            {"creator_username": "creator1", "topic": "news", "topic_count": 2},
        ]
        db = _make_stats_db_multi(creator_rows, topic_rows)

        result = await get_stats(db, user_id, stat_type="creator_details")

        assert result.success is True
        topics = result.data["creators"][0]["top_topics"]
        assert len(topics) == 3
        assert topics[0]["topic"] == "tech"
        assert topics[2]["topic"] == "coding"

    async def test_creator_details_no_classifications(self):
        """creator_details returns creators with empty topics when nothing is classified."""
        user_id = uuid4()
        creator_rows = [
            {
                "creator_username": "creator1",
                "item_count": 30,
                "first_seen": datetime(2025, 1, 1, tzinfo=UTC),
                "last_seen": datetime(2025, 6, 1, tzinfo=UTC),
            },
        ]
        topic_rows = []  # No classifications
        db = _make_stats_db_multi(creator_rows, topic_rows)

        result = await get_stats(db, user_id, stat_type="creator_details")

        assert result.success is True
        assert result.data["creators"][0]["top_topics"] == []

    async def test_creator_details_mixed_classification(self):
        """creator_details handles mix of classified and unclassified creators."""
        user_id = uuid4()
        creator_rows = [
            {
                "creator_username": "classified_creator",
                "item_count": 40,
                "first_seen": datetime(2024, 6, 1, tzinfo=UTC),
                "last_seen": datetime(2025, 6, 1, tzinfo=UTC),
            },
            {
                "creator_username": "unclassified_creator",
                "item_count": 20,
                "first_seen": datetime(2025, 3, 1, tzinfo=UTC),
                "last_seen": datetime(2025, 5, 1, tzinfo=UTC),
            },
        ]
        topic_rows = [
            {"creator_username": "classified_creator", "topic": "food", "topic_count": 15},
        ]
        db = _make_stats_db_multi(creator_rows, topic_rows)

        result = await get_stats(db, user_id, stat_type="creator_details")

        assert result.success is True
        assert len(result.data["creators"][0]["top_topics"]) == 1
        assert result.data["creators"][1]["top_topics"] == []


# ---------------------------------------------------------------------------
# Tests: field_distribution
# ---------------------------------------------------------------------------


class TestFieldDistribution:
    async def test_field_distribution_missing_field(self):
        """field_distribution returns error when field param is missing."""
        user_id = uuid4()
        db = AsyncMock()

        result = await get_stats(db, user_id, stat_type="field_distribution")

        assert result.success is False
        assert "'field' is required" in result.error

    async def test_field_distribution_invalid_field(self):
        """field_distribution returns error for non-allowlisted field."""
        user_id = uuid4()
        db = AsyncMock()

        result = await get_stats(db, user_id, stat_type="field_distribution", field="bad_field")

        assert result.success is False
        assert "Invalid field" in result.error

    async def test_field_distribution_music_name(self):
        """field_distribution groups by music_name and returns counts."""
        user_id = uuid4()
        rows = [
            {"field_value": "Original Sound", "item_count": 120},
            {"field_value": "Funny Song", "item_count": 45},
            {"field_value": "Chill Beats", "item_count": 30},
        ]
        db = _make_stats_db_rows(rows)

        result = await get_stats(db, user_id, stat_type="field_distribution", field="music_name")

        assert result.success is True
        assert result.data["field"] == "music_name"
        assert len(result.data["distribution"]) == 3
        assert result.data["distribution"][0]["value"] == "Original Sound"
        assert result.data["distribution"][0]["count"] == 120

    async def test_field_distribution_media_type(self):
        """field_distribution groups by media_type and returns counts."""
        user_id = uuid4()
        rows = [
            {"field_value": "video", "item_count": 700},
            {"field_value": "image", "item_count": 100},
            {"field_value": "slideshow", "item_count": 47},
        ]
        db = _make_stats_db_rows(rows)

        result = await get_stats(db, user_id, stat_type="field_distribution", field="media_type")

        assert result.success is True
        assert result.data["field"] == "media_type"
        assert len(result.data["distribution"]) == 3

    async def test_field_distribution_interaction_type(self):
        """field_distribution groups by interaction_type and returns counts."""
        user_id = uuid4()
        rows = [
            {"field_value": "liked", "item_count": 500},
            {"field_value": "favorited", "item_count": 347},
        ]
        db = _make_stats_db_rows(rows)

        result = await get_stats(
            db, user_id, stat_type="field_distribution", field="interaction_type"
        )

        assert result.success is True
        assert result.data["field"] == "interaction_type"
        assert len(result.data["distribution"]) == 2

    async def test_field_distribution_all_null(self):
        """field_distribution returns helpful note when all values are NULL."""
        user_id = uuid4()
        db = _make_stats_db_rows([])

        result = await get_stats(db, user_id, stat_type="field_distribution", field="music_name")

        assert result.success is True
        assert result.data["distribution"] == []
        assert "note" in result.data

    async def test_field_distribution_user_isolation(self):
        """field_distribution passes user_id to query for isolation."""
        user_id = uuid4()
        db = _make_stats_db_rows([])

        await get_stats(db, user_id, stat_type="field_distribution", field="music_name")

        call_args = db.execute.call_args_list[0]
        params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params", {})
        assert params.get("uid") == str(user_id)


# ---------------------------------------------------------------------------
# Tests: schema
# ---------------------------------------------------------------------------


class TestAggregationSchema:
    def test_get_stats_schema_includes_new_stat_types(self):
        """get_stats schema enum includes creator_details and field_distribution."""
        assert "creator_details" in _VALID_STAT_TYPES
        assert "field_distribution" in _VALID_STAT_TYPES

    def test_get_stats_schema_has_field_param(self):
        """get_stats tool definition includes the optional field parameter."""
        definitions = get_tool_definitions()
        stats_def = next(d for d in definitions if d["name"] == "get_stats")

        assert "field" in stats_def["input_schema"]["properties"]
        field_schema = stats_def["input_schema"]["properties"]["field"]
        assert field_schema["type"] == "string"
        assert set(field_schema["enum"]) == _AGGREGATE_FIELDS

    def test_aggregate_fields_allowlist(self):
        """Allowlist contains the expected fields."""
        assert _AGGREGATE_FIELDS == frozenset(
            {"music_name", "creator_username", "media_type", "interaction_type"}
        )
