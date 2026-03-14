"""Tests for Gemini client (classification and visual analysis)."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.gemini import analyze_visual, classify

# ---------------------------------------------------------------------------
# classify
# ---------------------------------------------------------------------------


class TestClassify:
    @pytest.mark.asyncio
    async def test_classify_success(self):
        classification = {
            "affect": {"label": "funny", "confidence": 0.9},
            "topic": {"label": "food", "confidence": 0.8},
        }
        mock_response = httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": json.dumps(classification)}]}}]},
        )
        with patch("app.services.gemini.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.post = AsyncMock(return_value=mock_response)

            result = await classify(
                api_key="test-key",
                caption="Funny cooking video",
                subtitle=None,
                hashtags=["food", "cooking"],
                creator_username="chef123",
                music_name=None,
            )

        assert result.success is True
        assert result.raw_classification == classification

    @pytest.mark.asyncio
    async def test_classify_no_metadata_returns_error(self):
        result = await classify(
            api_key="test-key",
            caption=None,
            subtitle=None,
            hashtags=None,
            creator_username=None,
            music_name=None,
        )
        assert result.success is False
        assert "No metadata" in result.error

    @pytest.mark.asyncio
    async def test_classify_api_error(self):
        mock_response = httpx.Response(500, text="Internal Server Error")
        with patch("app.services.gemini.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.post = AsyncMock(return_value=mock_response)

            result = await classify(
                api_key="test-key",
                caption="test",
                subtitle=None,
                hashtags=None,
                creator_username=None,
                music_name=None,
            )

        assert result.success is False
        assert "500" in result.error

    @pytest.mark.asyncio
    async def test_classify_timeout(self):
        with patch("app.services.gemini.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

            result = await classify(
                api_key="test-key",
                caption="test",
                subtitle=None,
                hashtags=None,
                creator_username=None,
                music_name=None,
            )

        assert result.success is False
        assert "timed out" in result.error

    @pytest.mark.asyncio
    async def test_classify_invalid_json_response(self):
        mock_response = httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "not valid json {{{"}]}}]},
        )
        with patch("app.services.gemini.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.post = AsyncMock(return_value=mock_response)

            result = await classify(
                api_key="test-key",
                caption="test",
                subtitle=None,
                hashtags=None,
                creator_username=None,
                music_name=None,
            )

        assert result.success is False
        assert "parse" in result.error.lower()

    @pytest.mark.asyncio
    async def test_classify_builds_context_from_all_fields(self):
        mock_response = httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "{}"}]}}]},
        )
        with patch("app.services.gemini.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.post = AsyncMock(return_value=mock_response)

            await classify(
                api_key="test-key",
                caption="caption",
                subtitle="transcript text",
                hashtags=["tag1"],
                creator_username="user1",
                music_name="song1",
            )

            # Check prompt contains all metadata
            call_args = mock_client.return_value.post.call_args
            body = call_args.kwargs["json"]
            prompt_text = body["contents"][0]["parts"][0]["text"]
            assert "caption" in prompt_text
            assert "transcript text" in prompt_text
            assert "tag1" in prompt_text
            assert "user1" in prompt_text
            assert "song1" in prompt_text


# ---------------------------------------------------------------------------
# analyze_visual
# ---------------------------------------------------------------------------


class TestAnalyzeVisual:
    @pytest.mark.asyncio
    async def test_analyze_visual_success(self):
        analysis = {
            "description": "A person cooking pasta",
            "objects": ["pan", "pasta", "kitchen"],
            "text_detected": "Recipe: Easy Pasta",
        }
        mock_response = httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {"parts": [{"text": json.dumps(analysis)}]},
                        "groundingMetadata": {
                            "groundingChunks": [
                                {"web": {"uri": "https://example.com", "title": "Example"}}
                            ]
                        },
                    }
                ]
            },
        )
        with patch("app.services.gemini.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.post = AsyncMock(return_value=mock_response)

            result = await analyze_visual(
                api_key="test-key",
                image_url="https://example.com/thumb.jpg",
                caption="cooking video",
            )

        assert result.success is True
        assert result.description == "A person cooking pasta"
        assert "pan" in result.objects
        assert result.text_detected == "Recipe: Easy Pasta"
        assert len(result.grounding_sources) == 1

    @pytest.mark.asyncio
    async def test_analyze_visual_no_grounding(self):
        analysis = {"description": "A cat", "objects": ["cat"], "text_detected": None}
        mock_response = httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {"parts": [{"text": json.dumps(analysis)}]},
                    }
                ]
            },
        )
        with patch("app.services.gemini.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.post = AsyncMock(return_value=mock_response)

            result = await analyze_visual(
                api_key="test-key",
                image_url="https://example.com/cat.jpg",
            )

        assert result.success is True
        assert result.grounding_sources == []

    @pytest.mark.asyncio
    async def test_analyze_visual_timeout(self):
        with patch("app.services.gemini.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

            result = await analyze_visual(
                api_key="test-key",
                image_url="https://example.com/thumb.jpg",
            )

        assert result.success is False
        assert "timed out" in result.error
