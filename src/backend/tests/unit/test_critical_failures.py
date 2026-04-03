"""Tests for critical failure gaps (4.10).

Covers:
- Entity API rate limiting and timeout handling
- DB constraint violations during cache writes
- Stale conversation handling
- Agent cost controls under concurrent pressure
- Graceful degradation when external services fail
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from app.services.agent import (
    MAX_TOOL_CALLS_PER_HOUR,
    _check_hourly_limit,
    _hourly_counts,
    _record_tool_call,
    run_agent,
)
from app.services.agent_tools import AgentToolResult, resolve_entity
from app.services.entity_resolvers import (
    resolve_book,
    resolve_movie_or_tv,
    resolve_music,
    resolve_place,
)

# ---------------------------------------------------------------------------
# Entity API rate limit / timeout failures
# ---------------------------------------------------------------------------


class TestEntityRateLimitAndTimeout:
    """Test entity resolvers handle HTTP 429 and timeouts gracefully."""

    @pytest.mark.asyncio
    async def test_google_maps_429_returns_error(self):
        """Google Maps 429 should not raise, just return error."""
        mock_response = httpx.Response(429, json={"error": "rate limited"})
        with patch("app.services.entity_resolvers._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await resolve_place("key", "test")

        assert result.success is False
        assert "429" in result.error

    @pytest.mark.asyncio
    async def test_tmdb_429_returns_error(self):
        """TMDB 429 should not raise, just return error."""
        mock_response = httpx.Response(429, json={})
        with patch("app.services.entity_resolvers._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await resolve_movie_or_tv("key", "test")

        assert result.success is False
        assert "429" in result.error

    @pytest.mark.asyncio
    async def test_books_429_returns_error(self):
        """Google Books 429 should not raise, just return error."""
        mock_response = httpx.Response(429, json={})
        with patch("app.services.entity_resolvers._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await resolve_book(None, "test")

        assert result.success is False
        assert "429" in result.error

    @pytest.mark.asyncio
    async def test_spotify_timeout_returns_error(self):
        """Spotify timeout should return error, not raise."""
        token_path = "app.services.entity_resolvers._get_spotify_token"
        with patch(token_path, new_callable=AsyncMock) as mock_token:
            mock_token.return_value = "test-token"
            with patch("app.services.entity_resolvers._get_client") as mock_get_client:
                mock_client = AsyncMock()
                mock_get_client.return_value = mock_client
                mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

                result = await resolve_music("id", "secret", "test query")

        assert result.success is False
        assert "timed out" in result.error

    @pytest.mark.asyncio
    async def test_connection_error_returns_error(self):
        """Connection errors should be handled gracefully."""
        with patch("app.services.entity_resolvers._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

            result = await resolve_place("key", "test")

        assert result.success is False
        assert "failed" in result.error.lower()


# ---------------------------------------------------------------------------
# DB constraint violations during cache writes
# ---------------------------------------------------------------------------


class TestDBConstraintOnCacheWrite:
    """Test that DB errors during cache writes are caught and don't crash."""

    # test_classify_db_flush_error_returns_error removed — classify tool removed in pipeline v2

    @pytest.mark.asyncio
    async def test_resolve_entity_db_flush_error_returns_error(self):
        """If db.flush() fails during entity cache write, return error."""
        user_id = uuid4()
        event_id = uuid4()

        event = MagicMock()
        event.id = event_id
        event.user_id = user_id
        event.cached_entities = []

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = event
        db.execute = AsyncMock(return_value=result_mock)
        db.flush = AsyncMock(side_effect=Exception("serialization failure"))

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

            settings = MagicMock()
            settings.google_maps_api_key = "k"
            settings.google_books_api_key = "k"
            settings.tmdb_api_key = "k"
            settings.spotify_client_id = "k"
            settings.spotify_client_secret = "k"

            result = await resolve_entity(db, settings, event_id, user_id, "book", "Test")

        assert result.success is False
        assert "failed" in result.error.lower()


# ---------------------------------------------------------------------------
# Stale conversation handling
# ---------------------------------------------------------------------------


class TestStaleConversation:
    """Test chat endpoint handles stale/deleted conversations."""

    async def test_deleted_conversation_returns_404(self):
        """If a conversation was deleted between requests, return 404."""
        from app.config import get_settings
        from app.core.rate_limit import check_chat_rate_limit
        from app.db.session import get_db
        from app.main import app
        from app.models.auth import AuthenticatedUser

        original_overrides = app.dependency_overrides.copy()

        user_id = uuid4()
        user = AuthenticatedUser(id=user_id, email="test@test.com")
        deleted_conv_id = uuid4()

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # Conversation gone
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        app.dependency_overrides[check_chat_rate_limit] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_settings] = lambda: MagicMock(
            anthropic_api_key="k",
            supabase_url="https://test.supabase.co",
            supabase_jwt_secret="secret",
        )

        try:
            from httpx import ASGITransport, AsyncClient

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/chat",
                    json={"message": "hello", "conversation_id": str(deleted_conv_id)},
                )

            assert response.status_code == 404
        finally:
            app.dependency_overrides = original_overrides


# ---------------------------------------------------------------------------
# Agent cost controls under pressure
# ---------------------------------------------------------------------------


class TestAgentCostControls:
    """Test that agent cost controls hold under concurrent/rapid usage."""

    def setup_method(self):
        _hourly_counts.clear()

    def test_hourly_limit_boundary_exact(self):
        """Exactly MAX_TOOL_CALLS_PER_HOUR calls should be allowed."""
        user_id = "boundary-user"
        for _ in range(MAX_TOOL_CALLS_PER_HOUR - 1):
            _record_tool_call(user_id)

        # Should allow one more
        assert _check_hourly_limit(user_id) is True

        _record_tool_call(user_id)
        # Now at limit — should block
        assert _check_hourly_limit(user_id) is False

    def test_multiple_users_isolated(self):
        """Rate limits are per-user, not global."""
        for _ in range(MAX_TOOL_CALLS_PER_HOUR):
            _record_tool_call("user-a")

        assert _check_hourly_limit("user-a") is False
        assert _check_hourly_limit("user-b") is True  # Different user, not limited

    async def test_agent_respects_both_limits_simultaneously(self):
        """Agent loop should enforce both per-query and hourly limits."""
        user_id = uuid4()
        user_id_str = str(user_id)

        # Pre-fill hourly to near limit
        now = time.time()
        _hourly_counts[user_id_str] = [now] * (MAX_TOOL_CALLS_PER_HOUR - 5)

        def _text_block(text):
            block = MagicMock()
            block.type = "text"
            block.text = text
            return block

        def _tool_block():
            block = MagicMock()
            block.type = "tool_use"
            block.name = "query_items"
            block.input = {"search_text": "x"}
            block.id = f"tool_{uuid4()}"
            return block

        # Build responses: tool calls then final text
        tool_resp = MagicMock()
        tool_resp.content = [_tool_block()]
        tool_resp.usage = MagicMock(input_tokens=10, output_tokens=10)

        final_resp = MagicMock()
        final_resp.content = [_text_block("Done.")]
        final_resp.usage = MagicMock(input_tokens=10, output_tokens=10)

        call_count = 0

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count > 10:
                return final_resp
            return tool_resp

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=mock_create)

        with (
            patch("app.services.agent._get_anthropic_client", return_value=mock_client),
            patch("app.services.agent._dispatch_tool", new_callable=AsyncMock) as mock_dispatch,
        ):
            mock_dispatch.return_value = AgentToolResult(success=True, data={})

            events = []
            async for event in run_agent(
                user_message="test",
                conversation_history=[],
                db=MagicMock(),
                settings=MagicMock(
                    anthropic_api_key="test-key",
                    max_tool_calls_per_query=50,
                    max_tool_calls_per_hour=200,
                ),
                user_id=user_id,
            ):
                events.append(event)

        # Should have been limited by hourly (only ~5 calls remaining)
        assert mock_dispatch.call_count <= 5

    def test_old_entries_dont_count_towards_limit(self):
        """Entries older than 1 hour should be pruned and not count."""
        user_id = "prune-test"
        old = time.time() - 7200  # 2 hours ago
        _hourly_counts[user_id] = [old] * 1000  # 1000 old entries

        # Should be under limit after pruning
        assert _check_hourly_limit(user_id) is True
        assert len(_hourly_counts[user_id]) == 0


# ---------------------------------------------------------------------------
# Agent graceful degradation
# ---------------------------------------------------------------------------


class TestAgentGracefulDegradation:
    """Test that agent continues gracefully when individual tools fail."""

    def setup_method(self):
        _hourly_counts.clear()

    async def test_tool_failure_does_not_crash_agent_loop(self):
        """If a tool returns an error, agent loop continues and Claude explains."""

        def _text_block(text):
            block = MagicMock()
            block.type = "text"
            block.text = text
            return block

        def _tool_block():
            block = MagicMock()
            block.type = "tool_use"
            block.name = "resolve_entity"
            block.input = {
                "media_event_id": str(uuid4()),
                "entity_type": "place",
                "entity_query": "test place",
            }
            block.id = "tool_1"
            return block

        tool_resp = MagicMock()
        tool_resp.content = [_tool_block()]
        tool_resp.usage = MagicMock(input_tokens=10, output_tokens=10)

        text_resp = MagicMock()
        text_resp.content = [_text_block("Sorry, classification failed for that item.")]
        text_resp.usage = MagicMock(input_tokens=10, output_tokens=10)

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=[tool_resp, text_resp])

        with (
            patch("app.services.agent._get_anthropic_client", return_value=mock_client),
            patch("app.services.agent._dispatch_tool", new_callable=AsyncMock) as mock_dispatch,
        ):
            # Tool fails
            mock_dispatch.return_value = AgentToolResult(
                success=False, error="Entity resolution timed out"
            )

            events = []
            async for event in run_agent(
                user_message="find that restaurant from my video",
                conversation_history=[],
                db=MagicMock(),
                settings=MagicMock(
                    anthropic_api_key="test-key",
                    max_tool_calls_per_query=50,
                    max_tool_calls_per_hour=200,
                ),
                user_id=uuid4(),
            ):
                events.append(event)

        # Agent should still produce output despite tool failure
        token_events = [e for e in events if e.event == "token"]
        assert len(token_events) > 0
        done_events = [e for e in events if e.event == "done"]
        assert len(done_events) == 1

    async def test_unexpected_exception_in_agent_yields_error(self):
        """Unexpected exceptions should yield error + done, not crash."""
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=RuntimeError("unexpected crash"))

        with patch("app.services.agent._get_anthropic_client", return_value=mock_client):
            events = []
            async for event in run_agent(
                user_message="hi",
                conversation_history=[],
                db=MagicMock(),
                settings=MagicMock(
                    anthropic_api_key="test-key",
                    max_tool_calls_per_query=50,
                    max_tool_calls_per_hour=200,
                ),
                user_id=uuid4(),
            ):
                events.append(event)

        event_types = [e.event for e in events]
        assert "error" in event_types
        assert "done" in event_types
