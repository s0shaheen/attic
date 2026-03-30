"""Tests for Instagram pipeline integration.

Covers:
- Instagram Apify response mapping (_map_instagram_apify_to_update)
- Instagram platform ID extraction (_extract_ig_platform_id_or_hash)
- Dev mode fake Instagram Apify responses
- Lambda handler source_platform passthrough
- Instagram collection import helper
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.pipeline import (
    _extract_ig_platform_id_or_hash,
    _fake_ig_apify_response,
    _map_instagram_apify_to_update,
)

# Ensure the lambdas directory is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lambdas"))

from pipeline.handler import handler  # noqa: E402

# ---------------------------------------------------------------------------
# _extract_ig_platform_id_or_hash
# ---------------------------------------------------------------------------


class TestExtractIgPlatformIdOrHash:
    def test_extracts_shortcode_from_reel_url(self):
        pid = _extract_ig_platform_id_or_hash(
            "https://www.instagram.com/reel/DVaDM79EwOV/", "upload123"
        )
        assert pid == "DVaDM79EwOV"

    def test_extracts_shortcode_from_post_url(self):
        pid = _extract_ig_platform_id_or_hash(
            "https://www.instagram.com/p/CqwTnSTuWWJ/", "upload123"
        )
        assert pid == "CqwTnSTuWWJ"

    def test_extracts_shortcode_from_tv_url(self):
        pid = _extract_ig_platform_id_or_hash(
            "https://www.instagram.com/tv/CXyz123_ab/", "upload123"
        )
        assert pid == "CXyz123_ab"

    def test_fallback_to_hash_for_unknown_url(self):
        pid = _extract_ig_platform_id_or_hash(
            "https://www.instagram.com/stories/user/123/", "upload123"
        )
        # Should return a deterministic hash, not None
        assert pid is not None
        assert len(pid) > 0

    def test_deterministic_for_same_input(self):
        pid1 = _extract_ig_platform_id_or_hash("https://www.instagram.com/stories/x/1/", "up1")
        pid2 = _extract_ig_platform_id_or_hash("https://www.instagram.com/stories/x/1/", "up1")
        assert pid1 == pid2


# ---------------------------------------------------------------------------
# _map_instagram_apify_to_update
# ---------------------------------------------------------------------------


class TestMapInstagramApifyToUpdate:
    def _make_apify_response(self, **overrides) -> dict:
        base = {
            "shortCode": "DVaDM79EwOV",
            "url": "https://www.instagram.com/reel/DVaDM79EwOV/",
            "caption": "Best pizza in NYC",
            "ownerUsername": "foodie_sarah",
            "ownerFullName": "Sarah Eats",
            "ownerId": "12345",
            "timestamp": "2025-06-15T12:00:00.000Z",
            "likesCount": 5000,
            "commentsCount": 200,
            "type": "Video",
            "displayUrl": "https://instagram.fcdn.net/v/thumb.jpg",
            "hashtags": ["food", "nyc", "pizza"],
            "mentions": ["@friend"],
            "images": [],
            "locationName": "New York",
            "videoDuration": 30,
            "videoUrl": "https://instagram.fcdn.net/v/video.mp4",
        }
        base.update(overrides)
        return base

    def test_maps_basic_fields(self):
        result = _map_instagram_apify_to_update(self._make_apify_response())

        assert result["caption_text"] == "Best pizza in NYC"
        assert result["creator_username"] == "foodie_sarah"
        assert result["creator_name"] == "Sarah Eats"
        assert result["creator_id"] == "12345"
        assert result["like_count"] == 5000
        assert result["comment_count"] == 200
        assert result["location_created"] == "New York"
        assert result["thumbnail_url"] == "https://instagram.fcdn.net/v/thumb.jpg"

    def test_maps_video_type(self):
        result = _map_instagram_apify_to_update(self._make_apify_response(type="Video"))
        assert result["media_type"] == "video"
        assert result["is_slideshow"] is False

    def test_maps_image_type(self):
        result = _map_instagram_apify_to_update(
            self._make_apify_response(type="Image", videoUrl=None, images=["img1.jpg"])
        )
        assert result["media_type"] == "image"

    def test_maps_sidecar_as_slideshow(self):
        result = _map_instagram_apify_to_update(
            self._make_apify_response(
                type="Sidecar", videoUrl=None, images=["img1.jpg", "img2.jpg"]
            )
        )
        assert result["media_type"] == "slideshow"
        assert result["is_slideshow"] is True
        assert result["image_count"] == 2

    def test_maps_hashtags(self):
        result = _map_instagram_apify_to_update(self._make_apify_response(hashtags=["food", "nyc"]))
        assert result["hashtags"] == ["food", "nyc"]

    def test_empty_hashtags_maps_to_none(self):
        result = _map_instagram_apify_to_update(self._make_apify_response(hashtags=[]))
        assert result["hashtags"] is None

    def test_maps_timestamp(self):
        result = _map_instagram_apify_to_update(
            self._make_apify_response(timestamp="2025-06-15T12:00:00.000Z")
        )
        assert result["video_created_at"] is not None
        assert result["video_created_at"].year == 2025
        assert result["video_created_at"].month == 6

    def test_none_timestamp(self):
        result = _map_instagram_apify_to_update(self._make_apify_response(timestamp=None))
        assert result["video_created_at"] is None

    def test_processing_state_set_to_enriched(self):
        result = _map_instagram_apify_to_update(self._make_apify_response())
        assert result["processing_state"] == "enriched"

    def test_video_duration_mapped(self):
        result = _map_instagram_apify_to_update(self._make_apify_response(videoDuration=30))
        assert result["video_duration_seconds"] == 30


# ---------------------------------------------------------------------------
# _fake_ig_apify_response
# ---------------------------------------------------------------------------


class TestFakeIgApifyResponse:
    def test_returns_dict_with_expected_keys(self):
        result = _fake_ig_apify_response("ABC123", 0)

        assert result["shortCode"] == "ABC123"
        assert "url" in result
        assert "caption" in result
        assert "ownerUsername" in result
        assert "type" in result

    def test_varies_by_index(self):
        r1 = _fake_ig_apify_response("A", 0)
        r2 = _fake_ig_apify_response("B", 1)

        assert r1["caption"] != r2["caption"]

    def test_maps_through_update_function(self):
        """Fake response should be valid input for _map_instagram_apify_to_update."""
        fake = _fake_ig_apify_response("TEST123", 3)
        result = _map_instagram_apify_to_update(fake)

        assert result["processing_state"] == "enriched"
        assert result["creator_username"] is not None


# ---------------------------------------------------------------------------
# Lambda handler passthrough
# ---------------------------------------------------------------------------


class TestLambdaHandlerPlatform:
    def test_handler_passes_source_platform(self):
        body = {
            "upload_id": "upload-1",
            "user_id": "user-1",
            "storage_path": "uploads/test/export.zip",
            "scope": "both",
            "source_platform": "instagram",
        }
        event = {"Records": [{"body": json.dumps(body)}]}
        ctx = MagicMock()
        ctx.aws_request_id = "req-1"

        mock_pipeline = MagicMock(return_value={"statusCode": 200, "body": "{}"})
        with patch("pipeline.handler.run_pipeline", mock_pipeline):
            handler(event, ctx)

        mock_pipeline.assert_called_once()
        assert mock_pipeline.call_args.kwargs["source_platform"] == "instagram"

    def test_handler_defaults_to_tiktok(self):
        body = {
            "upload_id": "upload-1",
            "user_id": "user-1",
            "storage_path": "uploads/test/export.zip",
        }
        event = {"Records": [{"body": json.dumps(body)}]}
        ctx = MagicMock()
        ctx.aws_request_id = "req-1"

        mock_pipeline = MagicMock(return_value={"statusCode": 200, "body": "{}"})
        with patch("pipeline.handler.run_pipeline", mock_pipeline):
            handler(event, ctx)

        mock_pipeline.assert_called_once()
        assert mock_pipeline.call_args.kwargs["source_platform"] == "tiktok"
