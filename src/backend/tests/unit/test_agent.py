"""Tests for agent loop and tool dispatch."""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.agent import (
    MAX_TOOL_CALLS_PER_HOUR,
    MAX_TOOL_CALLS_PER_QUERY,
    _check_hourly_limit,
    _dispatch_tool,
    _hourly_counts,
    _record_tool_call,
    _sse_done,
    _sse_error,
    _sse_token,
    run_agent,
)
from app.services.agent_tools import AgentToolResult

# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------


class TestSSEHelpers:
    def test_sse_token(self):
        event = _sse_token("hello")
        assert event.event == "token"
        assert json.loads(event.data) == {"text": "hello"}

    def test_sse_done_with_tokens(self):
        event = _sse_done(100)
        assert event.event == "done"
        assert json.loads(event.data) == {"total_tokens": 100}

    def test_sse_done_without_tokens(self):
        event = _sse_done()
        assert event.event == "done"
        assert json.loads(event.data) == {"total_tokens": None}

    def test_sse_error(self):
        event = _sse_error("something broke")
        assert event.event == "error"
        assert json.loads(event.data) == {"error": "something broke"}


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


class TestRateLimiting:
    def setup_method(self):
        _hourly_counts.clear()

    def test_check_hourly_limit_allows_under_limit(self):
        assert _check_hourly_limit("user1") is True

    def test_check_hourly_limit_blocks_over_limit(self):
        import time

        now = time.time()
        _hourly_counts["user1"] = [now] * MAX_TOOL_CALLS_PER_HOUR
        assert _check_hourly_limit("user1") is False

    def test_record_tool_call_creates_entry(self):
        _record_tool_call("user1")
        assert len(_hourly_counts["user1"]) == 1

    def test_old_entries_pruned(self):
        import time

        old_time = time.time() - 3700  # >1 hour ago
        _hourly_counts["user1"] = [old_time] * 100
        assert _check_hourly_limit("user1") is True
        assert len(_hourly_counts["user1"]) == 0


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------


class TestDispatchTool:
    @pytest.mark.asyncio
    async def test_dispatch_query_items(self):
        with patch("app.services.agent.query_items", new_callable=AsyncMock) as mock:
            mock.return_value = AgentToolResult(success=True, data={"items": []})
            await _dispatch_tool(
                "query_items",
                {"search_text": "food", "limit": 10, "unknown_key": "ignored"},
                MagicMock(),
                MagicMock(),
                uuid4(),
            )
            mock.assert_called_once()
            call_kwargs = mock.call_args
            assert "unknown_key" not in call_kwargs.kwargs

    @pytest.mark.asyncio
    async def test_dispatch_resolve_entity(self):
        with patch("app.services.agent.resolve_entity", new_callable=AsyncMock) as mock:
            mock.return_value = AgentToolResult(success=True, data={})
            await _dispatch_tool(
                "resolve_entity",
                {
                    "media_event_id": str(uuid4()),
                    "entity_type": "book",
                    "entity_query": "Atomic Habits",
                },
                MagicMock(),
                MagicMock(),
                uuid4(),
            )
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_unknown_tool_returns_error(self):
        result = await _dispatch_tool(
            "nonexistent_tool",
            {},
            MagicMock(),
            MagicMock(),
            uuid4(),
        )
        assert result.success is False
        assert "Unknown tool" in result.error


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------


def _make_mock_response(content_blocks, stop_reason="end_turn", input_tokens=10, output_tokens=20):
    """Create a mock Anthropic API response."""
    response = MagicMock()
    response.content = content_blocks
    response.stop_reason = stop_reason
    response.usage = MagicMock()
    response.usage.input_tokens = input_tokens
    response.usage.output_tokens = output_tokens
    return response


def _text_block(text):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _tool_use_block(tool_name, tool_input, tool_id="tool_1"):
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = tool_input
    block.id = tool_id
    return block


class TestRunAgent:
    def setup_method(self):
        _hourly_counts.clear()

    @pytest.mark.asyncio
    async def test_simple_text_response(self):
        """Agent returns text without tool calls."""
        mock_response = _make_mock_response([_text_block("Hello!")])

        with patch("app.services.agent._get_anthropic_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

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
        assert "token" in event_types
        assert "done" in event_types

        token_event = next(e for e in events if e.event == "token")
        assert json.loads(token_event.data)["text"] == "Hello!"

    @pytest.mark.asyncio
    async def test_tool_use_then_text(self):
        """Agent uses a tool, then returns text."""
        tool_response = _make_mock_response(
            [_tool_use_block("query_items", {"search_text": "food"})],
            stop_reason="tool_use",
        )
        text_response = _make_mock_response([_text_block("Found 5 items about food.")])

        with (
            patch("app.services.agent._get_anthropic_client") as mock_get_client,
            patch("app.services.agent._dispatch_tool", new_callable=AsyncMock) as mock_dispatch,
        ):
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(side_effect=[tool_response, text_response])
            mock_get_client.return_value = mock_client
            mock_dispatch.return_value = AgentToolResult(
                success=True, data={"items": [], "total": 5}
            )

            events = []
            async for event in run_agent(
                user_message="show me food",
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

        assert mock_client.messages.create.call_count == 2
        assert mock_dispatch.call_count == 1

        token_events = [e for e in events if e.event == "token"]
        assert any("food" in json.loads(e.data)["text"] for e in token_events)

    @pytest.mark.asyncio
    async def test_hourly_rate_limit_yields_error(self):
        """Agent rejects when hourly limit exceeded."""
        import time

        user_id = uuid4()
        _hourly_counts[str(user_id)] = [time.time()] * MAX_TOOL_CALLS_PER_HOUR

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
            user_id=user_id,
        ):
            events.append(event)

        event_types = [e.event for e in events]
        assert "error" in event_types
        assert "done" in event_types

    @pytest.mark.asyncio
    async def test_per_query_tool_limit(self):
        """Agent stops calling tools after MAX_TOOL_CALLS_PER_QUERY."""
        # Return tool_use blocks every time
        tool_response = _make_mock_response(
            [_tool_use_block("query_items", {"search_text": "x"})],
            stop_reason="tool_use",
        )
        final_response = _make_mock_response([_text_block("Done.")])

        call_count = 0

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            # After enough calls, return text to end loop
            if call_count > MAX_TOOL_CALLS_PER_QUERY + 2:
                return final_response
            return tool_response

        with (
            patch("app.services.agent._get_anthropic_client") as mock_get_client,
            patch("app.services.agent._dispatch_tool", new_callable=AsyncMock) as mock_dispatch,
        ):
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(side_effect=mock_create)
            mock_get_client.return_value = mock_client
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
                user_id=uuid4(),
            ):
                events.append(event)

        # dispatch should have been called exactly MAX_TOOL_CALLS_PER_QUERY times
        assert mock_dispatch.call_count == MAX_TOOL_CALLS_PER_QUERY

    @pytest.mark.asyncio
    async def test_api_error_yields_error_event(self):
        """Agent handles Anthropic API errors gracefully."""
        import anthropic

        with patch("app.services.agent._get_anthropic_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                side_effect=anthropic.APIError(
                    message="rate limited",
                    request=MagicMock(),
                    body=None,
                )
            )
            mock_get_client.return_value = mock_client

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

    @pytest.mark.asyncio
    async def test_tool_use_with_end_turn_still_processes_tools(self):
        """Regression: tool_use blocks with end_turn stop_reason must still be processed."""
        tool_response = _make_mock_response(
            [
                _text_block("Let me search..."),
                _tool_use_block("query_items", {"search_text": "food"}),
            ],
            stop_reason="end_turn",  # This was the bug — end_turn skipped tool processing
        )
        final_response = _make_mock_response([_text_block("Found results.")])

        with (
            patch("app.services.agent._get_anthropic_client") as mock_get_client,
            patch("app.services.agent._dispatch_tool", new_callable=AsyncMock) as mock_dispatch,
        ):
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(side_effect=[tool_response, final_response])
            mock_get_client.return_value = mock_client
            mock_dispatch.return_value = AgentToolResult(
                success=True, data={"items": [], "total": 0}
            )

            events = []
            async for event in run_agent(
                user_message="search food",
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

        # The tool MUST be dispatched even with end_turn
        assert mock_dispatch.call_count == 1

    @pytest.mark.asyncio
    async def test_conversation_history_passed_through(self):
        """Agent includes conversation history in messages."""
        history = [
            {"role": "user", "content": "first message"},
            {"role": "assistant", "content": "first response"},
        ]
        mock_response = _make_mock_response([_text_block("Reply.")])

        with patch("app.services.agent._get_anthropic_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            events = []
            async for event in run_agent(
                user_message="second message",
                conversation_history=history,
                db=MagicMock(),
                settings=MagicMock(
                    anthropic_api_key="test-key",
                    max_tool_calls_per_query=50,
                    max_tool_calls_per_hour=200,
                ),
                user_id=uuid4(),
            ):
                events.append(event)

        call_kwargs = mock_client.messages.create.call_args
        messages = call_kwargs.kwargs["messages"]
        assert len(messages) == 3  # 2 history + 1 current
        assert messages[0]["content"] == "first message"
        assert messages[2]["content"] == "second message"
