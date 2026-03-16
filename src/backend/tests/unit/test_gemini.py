"""Tests for Gemini client (classification and visual analysis)."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.gemini import _VISION_PROMPTS, VisionFocus, analyze_visual, classify

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
        with patch("app.services.gemini._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)

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
        with patch("app.services.gemini._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)

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
        with patch("app.services.gemini._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

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
        with patch("app.services.gemini._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)

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
        with patch("app.services.gemini._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)

            await classify(
                api_key="test-key",
                caption="caption",
                subtitle="transcript text",
                hashtags=["tag1"],
                creator_username="user1",
                music_name="song1",
            )

            # Check prompt contains all metadata
            call_args = mock_client.post.call_args
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
        with patch("app.services.gemini._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)

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
        with patch("app.services.gemini._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await analyze_visual(
                api_key="test-key",
                image_url="https://example.com/cat.jpg",
            )

        assert result.success is True
        assert result.grounding_sources == []

    @pytest.mark.asyncio
    async def test_analyze_visual_timeout(self):
        with patch("app.services.gemini._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

            result = await analyze_visual(
                api_key="test-key",
                image_url="https://example.com/thumb.jpg",
            )

        assert result.success is False
        assert "timed out" in result.error


# ---------------------------------------------------------------------------
# Vision focus modes
# ---------------------------------------------------------------------------


class TestVisionFocus:
    @pytest.mark.asyncio
    async def test_default_focus_is_general(self):
        """Calling without focus kwarg uses GENERAL prompt."""
        analysis = {"description": "test", "objects": [], "text_detected": None}
        mock_response = httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": json.dumps(analysis)}]}}]},
        )
        with patch("app.services.gemini._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)

            await analyze_visual(
                api_key="test-key",
                image_url="https://example.com/thumb.jpg",
            )

            call_args = mock_client.post.call_args
            body = call_args.kwargs["json"]
            prompt_text = body["contents"][0]["parts"][0]["text"]
            # GENERAL prompt contains these key phrases (backward compat regression)
            assert "brief description" in prompt_text
            assert "objects, people, or products" in prompt_text
            assert "text detected" in prompt_text.lower()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("focus", list(VisionFocus))
    async def test_each_focus_uses_its_prompt_template(self, focus):
        """Each focus mode produces a prompt matching its template."""
        analysis = {"description": "test", "objects": [], "text_detected": None}
        mock_response = httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": json.dumps(analysis)}]}}]},
        )
        with patch("app.services.gemini._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)

            await analyze_visual(
                api_key="test-key",
                image_url="https://example.com/thumb.jpg",
                focus=focus,
            )

            call_args = mock_client.post.call_args
            body = call_args.kwargs["json"]
            prompt_text = body["contents"][0]["parts"][0]["text"]
            assert prompt_text == _VISION_PROMPTS[focus]

    @pytest.mark.asyncio
    async def test_books_focus_contains_book_keywords(self):
        """BOOKS focus prompt mentions book-specific content."""
        analysis = {"description": "test", "objects": [], "text_detected": None}
        mock_response = httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": json.dumps(analysis)}]}}]},
        )
        with patch("app.services.gemini._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)

            await analyze_visual(
                api_key="test-key",
                image_url="https://example.com/thumb.jpg",
                focus=VisionFocus.BOOKS,
            )

            call_args = mock_client.post.call_args
            body = call_args.kwargs["json"]
            prompt_text = body["contents"][0]["parts"][0]["text"]
            assert "book" in prompt_text.lower()
            assert "title" in prompt_text.lower()
            assert "author" in prompt_text.lower()

    @pytest.mark.asyncio
    async def test_caption_prepended_with_focus(self):
        """Caption is prepended to the focus-specific prompt."""
        analysis = {"description": "test", "objects": [], "text_detected": None}
        mock_response = httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": json.dumps(analysis)}]}}]},
        )
        with patch("app.services.gemini._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)

            await analyze_visual(
                api_key="test-key",
                image_url="https://example.com/thumb.jpg",
                caption="great book recommendation",
                focus=VisionFocus.BOOKS,
            )

            call_args = mock_client.post.call_args
            body = call_args.kwargs["json"]
            prompt_text = body["contents"][0]["parts"][0]["text"]
            assert prompt_text.startswith("Context caption: great book recommendation")
            assert "book" in prompt_text.lower()

    def test_all_focus_modes_have_prompt_templates(self):
        """Every VisionFocus enum value has a corresponding prompt template."""
        for focus in VisionFocus:
            assert focus in _VISION_PROMPTS, f"Missing prompt template for {focus}"

    def test_all_prompts_request_json_output(self):
        """All prompt templates end with JSON output instruction."""
        for focus, prompt in _VISION_PROMPTS.items():
            assert "Return ONLY valid JSON" in prompt, f"{focus} prompt missing JSON instruction"
