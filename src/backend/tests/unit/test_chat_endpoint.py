"""Tests for the chat endpoint (POST /api/chat).

Tests cover authentication, request validation, conversation management,
SSE streaming behavior, and partial save on disconnect. All external
dependencies (DB, agent, auth) are mocked via FastAPI dependency overrides.
"""

import asyncio
import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.config import Settings, get_settings
from app.core.auth import get_current_user
from app.core.rate_limit import check_chat_rate_limit
from app.db.session import get_db
from app.main import app
from app.models.auth import AuthenticatedUser
from app.models.conversation import Message
from app.services.agent import SSEEvent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TEST_USER_ID = uuid4()
TEST_USER = AuthenticatedUser(id=TEST_USER_ID, email="test@test.com")


def _make_mock_settings() -> MagicMock:
    """Create a mock Settings object with required attributes."""
    settings = MagicMock(spec=Settings)
    settings.anthropic_api_key = "test-anthropic-key"
    settings.gemini_api_key = "test-gemini-key"
    settings.supabase_url = "https://test-project.supabase.co"
    settings.supabase_jwt_secret = "test-jwt-secret"
    return settings


def _parse_sse_events(response_text: str) -> list[dict]:
    """Parse SSE response text into a list of {event, data} dicts."""
    events = []
    current_event = {}
    for line in response_text.split("\n"):
        if line.startswith("event: "):
            current_event["event"] = line[len("event: ") :]
        elif line.startswith("data: "):
            raw = line[len("data: ") :]
            try:
                current_event["data"] = json.loads(raw)
            except json.JSONDecodeError:
                current_event["data"] = raw
        elif line == "" and current_event:
            events.append(current_event)
            current_event = {}
    if current_event:
        events.append(current_event)
    return events


def _make_mock_db(*, conversation_result=None, history_rows=None):
    """Create a mock AsyncSession that handles chat endpoint queries.

    The chat endpoint makes these DB calls:
    1. (optional) select(Conversation) — lookup existing conversation
    2. db.add(conversation) + db.flush() — create new conversation
    3. db.add(user_msg) + db.flush() — save user message
    4. select(Message) — load history
    5. db.add(assistant_msg) + db.commit() — save assistant response (in stream)

    Args:
        conversation_result: Return value for conversation lookup (scalar_one_or_none).
            None means "not found". Use a mock Conversation for "found".
        history_rows: List of mock Message objects for history query.
    """
    mock_db = AsyncMock()
    added_objects = []

    def track_add(obj):
        added_objects.append(obj)
        # Give conversations a UUID if they don't have one
        if hasattr(obj, "__tablename__") and not hasattr(obj, "_id_set"):
            pass  # Will be set by flush

    mock_db.add = MagicMock(side_effect=track_add)

    async def mock_flush():
        for obj in added_objects:
            if obj.id is None:
                obj.id = uuid4()

    mock_db.flush = AsyncMock(side_effect=mock_flush)
    mock_db.commit = AsyncMock()

    # Build execute side effects based on what the test needs
    if conversation_result is not None:
        # Two execute calls: conversation lookup, then history query
        conv_result = MagicMock()
        conv_result.scalar_one_or_none.return_value = conversation_result

        history_result = MagicMock()
        history_scalars = MagicMock()
        history_scalars.all.return_value = history_rows or []
        history_result.scalars.return_value = history_scalars

        mock_db.execute = AsyncMock(side_effect=[conv_result, history_result])
    else:
        # One execute call: history query only (new conversation)
        history_result = MagicMock()
        history_scalars = MagicMock()
        history_scalars.all.return_value = history_rows or []
        history_result.scalars.return_value = history_scalars

        mock_db.execute = AsyncMock(return_value=history_result)

    return mock_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _override_dependencies():
    """Override FastAPI dependencies for all tests in this module."""
    original_overrides = app.dependency_overrides.copy()

    mock_db = _make_mock_db()

    app.dependency_overrides[check_chat_rate_limit] = lambda: TEST_USER
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_settings] = _make_mock_settings

    yield

    app.dependency_overrides = original_overrides


# ---------------------------------------------------------------------------
# Test: Unauthenticated requests
# ---------------------------------------------------------------------------


class TestChatAuth:
    """Tests for authentication enforcement on the chat endpoint."""

    async def test_unauthenticated_request_returns_401(self, client):
        """Request without auth should be rejected with 401."""
        app.dependency_overrides.pop(check_chat_rate_limit, None)

        response = await client.post(
            "/api/chat",
            json={"message": "hello"},
        )

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Test: Request validation
# ---------------------------------------------------------------------------


class TestChatValidation:
    """Tests for ChatRequest validation."""

    async def test_empty_message_rejected(self, client):
        """Empty message string should fail validation."""
        response = await client.post(
            "/api/chat",
            json={"message": ""},
        )
        assert response.status_code == 422

    async def test_message_too_long_rejected(self, client):
        """Message exceeding 4000 chars should fail validation."""
        response = await client.post(
            "/api/chat",
            json={"message": "a" * 4001},
        )
        assert response.status_code == 422

    async def test_missing_message_field_rejected(self, client):
        """Request missing the message field should fail validation."""
        response = await client.post(
            "/api/chat",
            json={},
        )
        assert response.status_code == 422

    async def test_message_at_max_length_accepted(self, client):
        """Message exactly at 4000 chars should be accepted."""
        mock_db = _make_mock_db()
        app.dependency_overrides[get_db] = lambda: mock_db

        async def mock_run_agent(**kwargs):
            yield SSEEvent(event="token", data=json.dumps({"text": "ok"}))
            yield SSEEvent(event="done", data=json.dumps({"total_tokens": 10}))

        with patch("app.routers.chat.run_agent", side_effect=mock_run_agent):
            response = await client.post(
                "/api/chat",
                json={"message": "a" * 4000},
            )

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Test: Conversation management
# ---------------------------------------------------------------------------


class TestChatConversation:
    """Tests for conversation creation and lookup."""

    async def test_new_conversation_returns_meta_event(self, client):
        """When conversation_id is null, a new conversation is created."""
        mock_db = _make_mock_db()
        app.dependency_overrides[get_db] = lambda: mock_db

        async def mock_run_agent(**kwargs):
            yield SSEEvent(event="token", data=json.dumps({"text": "Hello!"}))
            yield SSEEvent(event="done", data=json.dumps({"total_tokens": 30}))

        with patch("app.routers.chat.run_agent", side_effect=mock_run_agent):
            response = await client.post(
                "/api/chat",
                json={"message": "hello"},
            )

        assert response.status_code == 200
        events = _parse_sse_events(response.text)

        meta_events = [e for e in events if e.get("event") == "meta"]
        assert len(meta_events) == 1
        # Should have a valid conversation_id (UUID string)
        conv_id = meta_events[0]["data"]["conversation_id"]
        assert len(conv_id) == 36  # UUID format

    async def test_existing_conversation_not_found_returns_404(self, client):
        """When conversation_id is provided but not found for user, return 404."""
        fake_conv_id = uuid4()

        # Mock DB that returns no conversation for lookup
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        app.dependency_overrides[get_db] = lambda: mock_db

        response = await client.post(
            "/api/chat",
            json={"message": "hello", "conversation_id": str(fake_conv_id)},
        )

        assert response.status_code == 404
        assert "Conversation not found" in response.json()["detail"]

    async def test_existing_conversation_owned_by_user_succeeds(self, client):
        """When conversation_id belongs to the user, proceed normally."""
        existing_conv_id = uuid4()
        mock_conversation = MagicMock()
        mock_conversation.id = existing_conv_id
        mock_conversation.user_id = TEST_USER_ID

        mock_db = _make_mock_db(conversation_result=mock_conversation)
        app.dependency_overrides[get_db] = lambda: mock_db

        async def mock_run_agent(**kwargs):
            yield SSEEvent(event="token", data=json.dumps({"text": "response"}))
            yield SSEEvent(event="done", data=json.dumps({"total_tokens": 20}))

        with patch("app.routers.chat.run_agent", side_effect=mock_run_agent):
            response = await client.post(
                "/api/chat",
                json={
                    "message": "hello",
                    "conversation_id": str(existing_conv_id),
                },
            )

        assert response.status_code == 200
        events = _parse_sse_events(response.text)

        meta_events = [e for e in events if e.get("event") == "meta"]
        assert len(meta_events) == 1
        assert meta_events[0]["data"]["conversation_id"] == str(existing_conv_id)


# ---------------------------------------------------------------------------
# Test: SSE streaming
# ---------------------------------------------------------------------------


class TestChatSSEStreaming:
    """Tests for SSE event streaming behavior."""

    async def test_valid_request_streams_meta_token_done(self, client):
        """A valid request should stream meta, token, and done events."""
        mock_db = _make_mock_db()
        app.dependency_overrides[get_db] = lambda: mock_db

        async def mock_run_agent(**kwargs):
            yield SSEEvent(event="token", data=json.dumps({"text": "Hello "}))
            yield SSEEvent(event="token", data=json.dumps({"text": "world!"}))
            yield SSEEvent(event="done", data=json.dumps({"total_tokens": 42}))

        with patch("app.routers.chat.run_agent", side_effect=mock_run_agent):
            response = await client.post(
                "/api/chat",
                json={"message": "hello"},
            )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        events = _parse_sse_events(response.text)
        event_types = [e["event"] for e in events]

        assert event_types[0] == "meta"

        token_events = [e for e in events if e["event"] == "token"]
        assert len(token_events) == 2
        assert token_events[0]["data"]["text"] == "Hello "
        assert token_events[1]["data"]["text"] == "world!"

        assert event_types[-1] == "done"
        done_event = [e for e in events if e["event"] == "done"][0]
        assert done_event["data"]["total_tokens"] == 42

    async def test_sse_response_headers(self, client):
        """SSE response should have correct caching and buffering headers."""
        mock_db = _make_mock_db()
        app.dependency_overrides[get_db] = lambda: mock_db

        async def mock_run_agent(**kwargs):
            yield SSEEvent(event="done", data=json.dumps({"total_tokens": 0}))

        with patch("app.routers.chat.run_agent", side_effect=mock_run_agent):
            response = await client.post(
                "/api/chat",
                json={"message": "hi"},
            )

        assert response.status_code == 200
        assert "no-cache" in response.headers.get("cache-control", "")
        assert response.headers.get("x-accel-buffering") == "no"

    async def test_agent_error_event_streamed(self, client):
        """When agent yields an error event, it should be streamed to client."""
        mock_db = _make_mock_db()
        app.dependency_overrides[get_db] = lambda: mock_db

        async def mock_run_agent(**kwargs):
            yield SSEEvent(
                event="error",
                data=json.dumps({"error": "Something went wrong"}),
            )
            yield SSEEvent(event="done", data=json.dumps({"total_tokens": 0}))

        with patch("app.routers.chat.run_agent", side_effect=mock_run_agent):
            response = await client.post(
                "/api/chat",
                json={"message": "hello"},
            )

        assert response.status_code == 200
        events = _parse_sse_events(response.text)

        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1
        assert error_events[0]["data"]["error"] == "Something went wrong"

    async def test_run_agent_receives_correct_parameters(self, client):
        """Verify run_agent is called with the right user_message, user_id, etc."""
        mock_db = _make_mock_db()
        app.dependency_overrides[get_db] = lambda: mock_db

        captured_kwargs = {}

        async def mock_run_agent(**kwargs):
            captured_kwargs.update(kwargs)
            yield SSEEvent(event="done", data=json.dumps({"total_tokens": 0}))

        with patch("app.routers.chat.run_agent", side_effect=mock_run_agent):
            response = await client.post(
                "/api/chat",
                json={"message": "search for cats"},
            )

        assert response.status_code == 200
        assert captured_kwargs["user_message"] == "search for cats"
        assert captured_kwargs["user_id"] == TEST_USER_ID
        assert isinstance(captured_kwargs["conversation_history"], list)


# ---------------------------------------------------------------------------
# Test: _format_sse helper
# ---------------------------------------------------------------------------


class TestFormatSSE:
    """Tests for the _format_sse helper function."""

    def test_format_sse_produces_correct_format(self):
        from app.routers.chat import _format_sse

        result = _format_sse("token", {"text": "hello"})
        assert result == 'event: token\ndata: {"text": "hello"}\n\n'

    def test_format_sse_meta_event(self):
        from app.routers.chat import _format_sse

        conv_id = str(uuid4())
        result = _format_sse("meta", {"conversation_id": conv_id})
        assert f'"conversation_id": "{conv_id}"' in result
        assert result.startswith("event: meta\n")
        assert result.endswith("\n\n")

    def test_format_sse_done_event(self):
        from app.routers.chat import _format_sse

        result = _format_sse("done", {"total_tokens": 42})
        parsed = json.loads(result.split("data: ")[1].strip())
        assert parsed["total_tokens"] == 42


# ---------------------------------------------------------------------------
# Test: Partial save on disconnect
# ---------------------------------------------------------------------------


class TestPartialSaveOnDisconnect:
    """Tests for the try/finally partial message save behavior.

    When a client disconnects mid-stream (tab close, network drop),
    the ASGI server cancels the generator via asyncio.CancelledError.
    The finally block should save whatever partial response has been
    accumulated to the database.
    """

    async def test_disconnect_mid_stream_saves_partial_message(self, client):
        """T7: Simulated disconnect should trigger partial message save.

        When run_agent raises CancelledError after yielding tokens,
        the finally block should save the accumulated partial text.
        """
        mock_db = _make_mock_db()
        app.dependency_overrides[get_db] = lambda: mock_db

        async def mock_run_agent(**kwargs):
            yield SSEEvent(event="token", data=json.dumps({"text": "Hello "}))
            yield SSEEvent(event="token", data=json.dumps({"text": "world"}))
            # Simulate ASGI cancellation on client disconnect
            raise asyncio.CancelledError()

        with patch("app.routers.chat.run_agent", side_effect=mock_run_agent):
            # The request may raise or return partial -- either way,
            # the finally block in event_stream should have executed.
            try:
                await client.post(
                    "/api/chat",
                    json={"message": "hello"},
                )
            except Exception:
                pass  # Transport error is expected when generator raises

        # Verify partial message was saved via finally block.
        # mock_db.add is called for: Conversation, user Message, partial Message
        added_messages = [
            c.args[0]
            for c in mock_db.add.call_args_list
            if isinstance(c.args[0], Message) and c.args[0].role == "assistant"
        ]
        assert len(added_messages) == 1
        assert added_messages[0].content == "Hello world"
        assert added_messages[0].token_count is None  # No token count for partial

        # commit should have been called (by the finally block)
        assert mock_db.commit.await_count >= 1

    async def test_normal_completion_finally_is_noop(self, client):
        """T8: Normal completion sets saved=True, so finally does not save again.

        When the done event is received and the message is saved normally,
        the finally block should be a no-op (no duplicate save).
        """
        mock_db = _make_mock_db()
        app.dependency_overrides[get_db] = lambda: mock_db

        async def mock_run_agent(**kwargs):
            yield SSEEvent(event="token", data=json.dumps({"text": "Complete "}))
            yield SSEEvent(event="token", data=json.dumps({"text": "response"}))
            yield SSEEvent(event="done", data=json.dumps({"total_tokens": 50}))

        with patch("app.routers.chat.run_agent", side_effect=mock_run_agent):
            response = await client.post(
                "/api/chat",
                json={"message": "hello"},
            )

        assert response.status_code == 200

        # Only one assistant message should have been saved (from the done handler)
        added_messages = [
            c.args[0]
            for c in mock_db.add.call_args_list
            if isinstance(c.args[0], Message) and c.args[0].role == "assistant"
        ]
        assert len(added_messages) == 1
        assert added_messages[0].content == "Complete response"
        assert added_messages[0].token_count == 50

        # commit should be called exactly once (from the done handler, not from finally)
        assert mock_db.commit.await_count == 1

    async def test_partial_save_db_failure_logged(self, client, caplog):
        """T9: DB failure in finally block is logged, not raised.

        When the partial save in the finally block fails (e.g., DB connection
        lost), the error should be caught and logged, not crash the server.
        """
        mock_db = _make_mock_db()
        # Make commit raise an exception (simulating DB failure in finally)
        mock_db.commit = AsyncMock(side_effect=Exception("DB connection lost"))
        app.dependency_overrides[get_db] = lambda: mock_db

        async def mock_run_agent(**kwargs):
            yield SSEEvent(event="token", data=json.dumps({"text": "Partial"}))
            raise asyncio.CancelledError()

        with (
            patch("app.routers.chat.run_agent", side_effect=mock_run_agent),
            caplog.at_level(logging.ERROR, logger="app.routers.chat"),
        ):
            try:
                await client.post(
                    "/api/chat",
                    json={"message": "hello"},
                )
            except Exception:
                pass  # Transport error is expected

        # Verify the error was logged (not raised)
        partial_save_failed_logs = [
            r for r in caplog.records if "partial_message_save_failed" in str(r.message)
        ]
        assert len(partial_save_failed_logs) >= 1

    async def test_disconnect_before_any_tokens_no_save(self, client):
        """T10: Disconnect before any tokens are received should not save anything.

        When CancelledError fires before any token events, full_response is empty
        and the finally block should be a no-op.
        """
        mock_db = _make_mock_db()
        app.dependency_overrides[get_db] = lambda: mock_db

        async def mock_run_agent(**kwargs):
            # Disconnect immediately — no tokens yielded
            raise asyncio.CancelledError()
            yield  # noqa: unreachable — makes this an async generator

        with patch("app.routers.chat.run_agent", side_effect=mock_run_agent):
            try:
                await client.post(
                    "/api/chat",
                    json={"message": "hello"},
                )
            except Exception:
                pass

        # No assistant message should have been saved
        added_messages = [
            c.args[0]
            for c in mock_db.add.call_args_list
            if isinstance(c.args[0], Message) and c.args[0].role == "assistant"
        ]
        assert len(added_messages) == 0
