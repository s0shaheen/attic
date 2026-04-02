"""Tests for graceful fallback when external APIs are unavailable."""

import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.services.agent import _hourly_counts, run_agent


class TestAnthropicClientUnavailable:
    def setup_method(self):
        _hourly_counts.clear()

    @pytest.mark.asyncio
    async def test_missing_api_key_yields_error_event(self):
        """When Anthropic API key is missing, agent yields a clean error+done."""
        with patch("app.services.agent._get_anthropic_client", return_value=None):
            events = []
            async for event in run_agent(
                user_message="hello",
                conversation_history=[],
                db=MagicMock(),
                settings=MagicMock(
                    anthropic_api_key="",
                    max_tool_calls_per_query=50,
                    max_tool_calls_per_hour=200,
                ),
                user_id=uuid4(),
            ):
                events.append(event)

        event_types = [e.event for e in events]
        assert "error" in event_types
        assert "done" in event_types

        error_event = next(e for e in events if e.event == "error")
        error_data = json.loads(error_event.data)
        assert "unavailable" in error_data["error"].lower()

    @pytest.mark.asyncio
    async def test_client_available_proceeds_normally(self):
        """When client is available, agent proceeds to call Claude."""
        from unittest.mock import AsyncMock

        mock_response = MagicMock()
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Hello!"
        mock_response.content = [text_block]
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

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
        assert "token" in event_types
        assert "done" in event_types
