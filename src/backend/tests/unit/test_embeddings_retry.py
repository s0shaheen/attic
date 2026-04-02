"""Tests for OpenAI embeddings retry/backoff logic."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.agent_tools import _embed_query


def _make_response(status_code: int, json_data: dict | None = None, headers: dict | None = None):
    """Create a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.headers = headers or {}

    if json_data:
        resp.json.return_value = json_data
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    else:
        resp.raise_for_status.return_value = None

    return resp


_SUCCESS_RESPONSE = _make_response(
    200,
    {"data": [{"embedding": [0.1, 0.2, 0.3]}]},
)


class TestEmbedQueryRetry:
    @pytest.mark.asyncio
    async def test_success_on_first_try(self):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=_SUCCESS_RESPONSE)

        with patch("app.services.agent_tools._get_openai_client", return_value=mock_client):
            result = await _embed_query("test-key", "hello world")

        assert result == [0.1, 0.2, 0.3]
        assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_429_then_succeeds(self):
        rate_limited = _make_response(429)
        success = _make_response(200, {"data": [{"embedding": [0.4, 0.5]}]})

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=[rate_limited, success])

        with (
            patch("app.services.agent_tools._get_openai_client", return_value=mock_client),
            patch("app.services.agent_tools.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await _embed_query("test-key", "hello")

        assert result == [0.4, 0.5]
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_retries_on_500_then_succeeds(self):
        error_resp = _make_response(500)
        success = _make_response(200, {"data": [{"embedding": [0.6]}]})

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=[error_resp, success])

        with (
            patch("app.services.agent_tools._get_openai_client", return_value=mock_client),
            patch("app.services.agent_tools.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await _embed_query("test-key", "hello")

        assert result == [0.6]

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        error_resp = _make_response(429)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=error_resp)

        with (
            patch("app.services.agent_tools._get_openai_client", return_value=mock_client),
            patch("app.services.agent_tools.asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(httpx.HTTPStatusError),
        ):
            await _embed_query("test-key", "hello")

        # 1 initial + 3 retries = 4 total
        assert mock_client.post.call_count == 4

    @pytest.mark.asyncio
    async def test_non_retryable_status_raises_immediately(self):
        """A 401 should not be retried."""
        unauthorized = _make_response(401)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=unauthorized)

        with (
            patch("app.services.agent_tools._get_openai_client", return_value=mock_client),
            pytest.raises(httpx.HTTPStatusError),
        ):
            await _embed_query("test-key", "hello")

        assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_respects_retry_after_header(self):
        rate_limited = _make_response(429, headers={"Retry-After": "2"})
        success = _make_response(200, {"data": [{"embedding": [0.7]}]})

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=[rate_limited, success])

        sleep_mock = AsyncMock()
        with (
            patch("app.services.agent_tools._get_openai_client", return_value=mock_client),
            patch("app.services.agent_tools.asyncio.sleep", sleep_mock),
        ):
            result = await _embed_query("test-key", "hello")

        assert result == [0.7]
        sleep_mock.assert_called_once_with(2.0)
