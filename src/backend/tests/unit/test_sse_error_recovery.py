"""Tests for SSE error recovery in the chat endpoint.

Verifies that unhandled exceptions in the event_stream() generator
produce clean error+done events instead of dropping the connection.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.config import Settings, get_settings
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
    settings = MagicMock(spec=Settings)
    settings.anthropic_api_key = "test-key"
    settings.chat_rate_limit_per_minute = 100
    return settings


def _make_mock_db():
    mock_db = AsyncMock()
    added_objects = []

    def track_add(obj):
        added_objects.append(obj)

    mock_db.add = MagicMock(side_effect=track_add)

    async def mock_flush():
        for obj in added_objects:
            if obj.id is None:
                obj.id = uuid4()

    mock_db.flush = AsyncMock(side_effect=mock_flush)
    mock_db.commit = AsyncMock()

    history_result = MagicMock()
    history_scalars = MagicMock()
    history_scalars.all.return_value = []
    history_result.scalars.return_value = history_scalars
    mock_db.execute = AsyncMock(return_value=history_result)

    return mock_db


def _parse_sse_events(response_text: str) -> list[dict]:
    events = []
    current_event = {}
    for line in response_text.split("\n"):
        if line.startswith("event: "):
            current_event["event"] = line[len("event: "):]
        elif line.startswith("data: "):
            raw = line[len("data: "):]
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _override_dependencies():
    original_overrides = app.dependency_overrides.copy()

    mock_db = _make_mock_db()

    app.dependency_overrides[check_chat_rate_limit] = lambda: TEST_USER
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_settings] = _make_mock_settings

    yield

    app.dependency_overrides = original_overrides


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSSEErrorRecovery:
    async def test_unhandled_exception_yields_error_done(self, client):
        """When run_agent raises an unexpected exception, the client still
        receives a clean error+done event pair instead of a dropped connection."""
        mock_db = _make_mock_db()
        app.dependency_overrides[get_db] = lambda: mock_db

        async def mock_run_agent(**kwargs):
            yield SSEEvent(event="token", data=json.dumps({"text": "partial "}))
            raise RuntimeError("unexpected failure in agent")

        with patch("app.routers.chat.run_agent", side_effect=mock_run_agent):
            response = await client.post(
                "/api/chat",
                json={"message": "hello"},
            )

        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        event_types = [e["event"] for e in events]

        assert "error" in event_types
        assert "done" in event_types

        error_event = next(e for e in events if e["event"] == "error")
        assert "went wrong" in error_event["data"]["error"].lower()

    async def test_clean_stream_not_affected(self, client):
        """Normal agent execution still works with the error recovery in place."""
        mock_db = _make_mock_db()
        app.dependency_overrides[get_db] = lambda: mock_db

        async def mock_run_agent(**kwargs):
            yield SSEEvent(event="token", data=json.dumps({"text": "Hello!"}))
            yield SSEEvent(event="done", data=json.dumps({"total_tokens": 42}))

        with patch("app.routers.chat.run_agent", side_effect=mock_run_agent):
            response = await client.post(
                "/api/chat",
                json={"message": "hi"},
            )

        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        event_types = [e["event"] for e in events]

        assert "meta" in event_types
        assert "token" in event_types
        assert "done" in event_types
        assert "error" not in event_types

    async def test_db_commit_failure_after_done_no_double_done(self, client):
        """When db.commit() fails after the agent's done event was already
        forwarded, the client should NOT receive a second done event."""
        mock_db = _make_mock_db()
        # Make commit raise — simulates DB failure when saving assistant message
        mock_db.commit.side_effect = Exception("DB connection lost")
        app.dependency_overrides[get_db] = lambda: mock_db

        async def mock_run_agent(**kwargs):
            yield SSEEvent(event="token", data=json.dumps({"text": "Hello!"}))
            yield SSEEvent(event="done", data=json.dumps({"total_tokens": 42}))

        with patch("app.routers.chat.run_agent", side_effect=mock_run_agent):
            response = await client.post(
                "/api/chat",
                json={"message": "hi"},
            )

        assert response.status_code == 200
        events = _parse_sse_events(response.text)

        # Should have exactly ONE done event, not two
        done_events = [e for e in events if e["event"] == "done"]
        assert len(done_events) == 1
