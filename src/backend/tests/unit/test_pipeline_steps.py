"""Unit tests for pipeline step functions and helpers in src/lambdas/pipeline/handler.py.

Tests pure/helper functions: URL normalization, platform ID extraction,
text fusion, Apify data mapping, engine creation, and handler entry point.

Note: The handler imports app.models.* (SQLAlchemy ORM models) that use
Python 3.10+ syntax (PEP 604 unions). We pre-seed sys.modules with
lightweight stubs so the handler can import cleanly on any Python version,
making tests fast and isolated from the full ORM chain.
"""

from __future__ import annotations

import hashlib
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

# Ensure the lambdas directory is on sys.path so we can import the handler
_lambdas_dir = str(Path(__file__).resolve().parents[3] / "lambdas")
if _lambdas_dir not in sys.path:
    sys.path.insert(0, _lambdas_dir)

from pipeline.handler import handler  # noqa: E402

from app.services.pipeline import (  # noqa: E402
    _extract_platform_id,
    _extract_platform_id_or_hash,
    _fuse_text,
    _get_engine,
    _map_apify_to_update,
    _normalize_tiktok_url,
)

# ---------------------------------------------------------------------------
# Helpers to build mock MediaEvent-like objects for _fuse_text
# ---------------------------------------------------------------------------


def _make_event(**kwargs: Any) -> SimpleNamespace:
    """Build a mock MediaEvent with defaults for all text-fusion fields."""
    defaults = {
        "caption_text": None,
        "hashtags": None,
        "subtitle_text": None,
        "creator_username": None,
        "music_name": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ==========================================================================
# 1. _normalize_tiktok_url
# ==========================================================================


class TestNormalizeTiktokUrl:
    def test_replaces_tiktokv_with_tiktok(self):
        url = "https://www.tiktokv.com/share/video/1234567890"
        assert _normalize_tiktok_url(url) == "https://www.tiktok.com/share/video/1234567890"

    def test_no_change_for_standard_tiktok_url(self):
        url = "https://www.tiktok.com/@user/video/1234567890"
        assert _normalize_tiktok_url(url) == url

    def test_no_change_for_vm_tiktok_url(self):
        url = "https://vm.tiktok.com/ZMRxyz123/"
        assert _normalize_tiktok_url(url) == url

    def test_preserves_query_params(self):
        url = "https://www.tiktokv.com/share/video/123?q=1&is_copy_url=1"
        result = _normalize_tiktok_url(url)
        assert result == "https://www.tiktok.com/share/video/123?q=1&is_copy_url=1"

    def test_empty_string(self):
        assert _normalize_tiktok_url("") == ""

    def test_no_change_for_unrelated_url(self):
        url = "https://www.youtube.com/watch?v=abc"
        assert _normalize_tiktok_url(url) == url


# ==========================================================================
# 2. _extract_platform_id
# ==========================================================================


class TestExtractPlatformId:
    def test_extracts_video_id_from_standard_url(self):
        url = "https://www.tiktok.com/@user/video/7123456789012345678"
        assert _extract_platform_id(url) == "7123456789012345678"

    def test_extracts_video_id_from_share_url(self):
        url = "https://www.tiktok.com/share/video/7123456789"
        assert _extract_platform_id(url) == "7123456789"

    def test_returns_none_for_short_url(self):
        url = "https://vm.tiktok.com/ZMRxyz123/"
        assert _extract_platform_id(url) is None

    def test_returns_none_for_no_video_path(self):
        url = "https://www.tiktok.com/@user"
        assert _extract_platform_id(url) is None

    def test_returns_none_for_empty_string(self):
        assert _extract_platform_id("") is None

    def test_extracts_from_url_with_query_params(self):
        url = "https://www.tiktok.com/@user/video/7123456789?is_copy=1"
        assert _extract_platform_id(url) == "7123456789"

    def test_returns_none_for_non_digit_after_video(self):
        url = "https://www.tiktok.com/@user/video/"
        assert _extract_platform_id(url) is None


# ==========================================================================
# 3. _extract_platform_id_or_hash
# ==========================================================================


class TestExtractPlatformIdOrHash:
    def test_returns_platform_id_when_present(self):
        url = "https://www.tiktok.com/@user/video/7123456789"
        result = _extract_platform_id_or_hash(url, "upload-123")
        assert result == "7123456789"

    def test_returns_deterministic_hash_for_short_url(self):
        url = "https://vm.tiktok.com/ZMRxyz123/"
        upload_id = "test-upload-id"
        result = _extract_platform_id_or_hash(url, upload_id)

        # Verify it is a valid UUID string
        uuid.UUID(result)  # Raises if invalid

        # Verify deterministic: same inputs produce same output
        result2 = _extract_platform_id_or_hash(url, upload_id)
        assert result == result2

    def test_different_upload_ids_produce_different_hashes(self):
        url = "https://vm.tiktok.com/ZMRxyz123/"
        result_a = _extract_platform_id_or_hash(url, "upload-a")
        result_b = _extract_platform_id_or_hash(url, "upload-b")
        assert result_a != result_b

    def test_hash_matches_generate_idempotency_key(self):
        """The hash path should delegate to generate_idempotency_key."""
        url = "https://vm.tiktok.com/ZMRxyz123/"
        upload_id = "upload-id-xyz"
        result = _extract_platform_id_or_hash(url, upload_id)

        # Compute expected value the same way as generate_idempotency_key
        composite = f"{upload_id}:{url}"
        hash_bytes = hashlib.sha256(composite.encode("utf-8")).digest()
        expected = str(uuid.UUID(bytes=hash_bytes[:16]))
        assert result == expected


# ==========================================================================
# 4. _fuse_text
# ==========================================================================


class TestFuseText:
    def test_all_fields_populated(self):
        event = _make_event(
            caption_text="funny cat video",
            hashtags=["cats", "funny"],
            subtitle_text="meow meow meow",
            creator_username="catperson",
            music_name="Original Sound",
        )
        result = _fuse_text(event)
        assert result == (
            "funny cat video | #cats #funny | meow meow meow | "
            "by @catperson | music: Original Sound"
        )

    def test_only_caption(self):
        event = _make_event(caption_text="just a caption")
        assert _fuse_text(event) == "just a caption"

    def test_only_hashtags(self):
        event = _make_event(hashtags=["travel", "japan"])
        assert _fuse_text(event) == "#travel #japan"

    def test_only_subtitle(self):
        event = _make_event(subtitle_text="speech to text output")
        assert _fuse_text(event) == "speech to text output"

    def test_only_creator(self):
        event = _make_event(creator_username="someuser")
        assert _fuse_text(event) == "by @someuser"

    def test_only_music(self):
        event = _make_event(music_name="Dance Monkey")
        assert _fuse_text(event) == "music: Dance Monkey"

    def test_empty_fields_returns_untitled(self):
        event = _make_event()
        assert _fuse_text(event) == "untitled tiktok"

    def test_empty_hashtag_list_returns_untitled(self):
        """An empty list [] is falsy, should be treated same as None."""
        event = _make_event(hashtags=[])
        assert _fuse_text(event) == "untitled tiktok"

    def test_caption_and_creator_only(self):
        event = _make_event(caption_text="check this out", creator_username="testuser")
        assert _fuse_text(event) == "check this out | by @testuser"

    def test_subtitle_and_music_only(self):
        event = _make_event(subtitle_text="hello world", music_name="Lofi Beats")
        assert _fuse_text(event) == "hello world | music: Lofi Beats"


# ==========================================================================
# 5. _map_apify_to_update
# ==========================================================================


class TestMapApifyToUpdate:
    def test_standard_video_all_fields(self):
        apify_data = {
            "text": "My caption",
            "authorMeta": {
                "name": "johndoe",
                "nickName": "John Doe",
                "id": "12345",
                "fans": 50000,
                "verified": True,
            },
            "musicMeta": {
                "musicId": "m789",
                "musicName": "Cool Song",
                "musicAuthor": "DJ Cool",
                "musicOriginal": False,
            },
            "videoMeta": {"duration": 30},
            "covers": {"default": "https://p16.tiktokcdn.com/cover.jpg"},
            "hashtags": [{"name": "fyp"}, {"name": "viral"}],
            "mentions": ["@friend1"],
            "playCount": 100000,
            "diggCount": 5000,
            "commentCount": 200,
            "shareCount": 100,
            "collectCount": 50,
            "createTime": 1700000000,
            "isAd": False,
            "isPinned": True,
            "locationCreated": "US",
            "effectStickers": ["sticker1"],
        }

        result = _map_apify_to_update(apify_data)

        assert result["caption_text"] == "My caption"
        assert result["hashtags"] == ["fyp", "viral"]
        assert result["mentions"] == ["@friend1"]
        assert result["creator_username"] == "johndoe"
        assert result["creator_name"] == "John Doe"
        assert result["creator_id"] == "12345"
        assert result["creator_followers"] == 50000
        assert result["creator_verified"] is True
        assert result["play_count"] == 100000
        assert result["like_count"] == 5000
        assert result["comment_count"] == 200
        assert result["share_count"] == 100
        assert result["collect_count"] == 50
        assert result["video_duration_seconds"] == 30
        assert result["is_ad"] is False
        assert result["is_pinned"] is True
        assert result["is_slideshow"] is False
        assert result["media_type"] == "video"
        assert result["image_count"] is None
        assert result["image_urls"] is None
        assert result["location_created"] == "US"
        assert result["music_id"] == "m789"
        assert result["music_name"] == "Cool Song"
        assert result["music_author"] == "DJ Cool"
        assert result["music_is_original"] is False
        assert result["effect_stickers"] == ["sticker1"]
        assert result["thumbnail_url"] == "https://p16.tiktokcdn.com/cover.jpg"
        assert result["processing_state"] == "enriched"

        # Timestamp conversion
        expected_dt = datetime.fromtimestamp(1700000000, tz=UTC)
        assert result["video_created_at"] == expected_dt

    def test_slideshow_multiple_images(self):
        apify_data = {
            "imagePost": True,
            "images": [
                "https://img1.tiktokcdn.com/1.jpg",
                "https://img2.tiktokcdn.com/2.jpg",
                "https://img3.tiktokcdn.com/3.jpg",
            ],
        }
        result = _map_apify_to_update(apify_data)
        assert result["media_type"] == "slideshow"
        assert result["is_slideshow"] is True
        assert result["image_count"] == 3
        assert len(result["image_urls"]) == 3

    def test_single_image(self):
        apify_data = {
            "images": ["https://img.tiktokcdn.com/photo.jpg"],
        }
        result = _map_apify_to_update(apify_data)
        assert result["media_type"] == "image"
        assert result["is_slideshow"] is False
        assert result["image_count"] == 1
        assert result["image_urls"] == ["https://img.tiktokcdn.com/photo.jpg"]

    def test_missing_optional_fields(self):
        """With a minimal Apify response, all optional fields default gracefully."""
        apify_data = {}
        result = _map_apify_to_update(apify_data)

        assert result["caption_text"] is None
        assert result["hashtags"] is None
        assert result["mentions"] is None
        assert result["creator_username"] is None
        assert result["creator_name"] is None
        assert result["creator_id"] is None
        assert result["creator_followers"] is None
        assert result["creator_verified"] is None
        assert result["play_count"] is None
        assert result["like_count"] is None
        assert result["comment_count"] is None
        assert result["share_count"] is None
        assert result["collect_count"] is None
        assert result["video_duration_seconds"] is None
        assert result["video_created_at"] is None
        assert result["is_ad"] is None
        assert result["is_pinned"] is None
        assert result["is_slideshow"] is False
        assert result["media_type"] == "video"
        assert result["image_count"] is None
        assert result["image_urls"] is None
        assert result["location_created"] is None
        assert result["music_id"] is None
        assert result["music_name"] is None
        assert result["music_author"] is None
        assert result["music_is_original"] is None
        assert result["effect_stickers"] is None
        assert result["thumbnail_url"] is None
        assert result["processing_state"] == "enriched"

    def test_timestamp_conversion_known_value(self):
        """Verify a known Unix timestamp converts to the correct UTC datetime."""
        apify_data = {"createTime": 1700000000}
        result = _map_apify_to_update(apify_data)
        expected = datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)
        assert result["video_created_at"] == expected

    def test_timestamp_epoch_zero_treated_as_missing(self):
        """createTime=0 is falsy in Python, so handler treats it as missing."""
        apify_data = {"createTime": 0}
        result = _map_apify_to_update(apify_data)
        assert result["video_created_at"] is None

    def test_timestamp_string_numeric(self):
        """createTime as a string should still be converted via int()."""
        apify_data = {"createTime": "1700000000"}
        result = _map_apify_to_update(apify_data)
        expected = datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)
        assert result["video_created_at"] == expected

    def test_timestamp_none_when_missing(self):
        apify_data = {}
        result = _map_apify_to_update(apify_data)
        assert result["video_created_at"] is None

    def test_hashtag_extraction_filters_non_dicts(self):
        """Only dict entries with 'name' key should be extracted."""
        apify_data = {
            "hashtags": [{"name": "valid"}, "invalid_string", {"name": "also_valid"}],
        }
        result = _map_apify_to_update(apify_data)
        assert result["hashtags"] == ["valid", "also_valid"]

    def test_hashtags_empty_list_becomes_none(self):
        apify_data = {"hashtags": []}
        result = _map_apify_to_update(apify_data)
        assert result["hashtags"] is None

    def test_creator_id_empty_string_becomes_none(self):
        """str('') or None should map to None for creator_id."""
        apify_data = {"authorMeta": {"id": ""}}
        result = _map_apify_to_update(apify_data)
        assert result["creator_id"] is None

    def test_music_id_empty_string_becomes_none(self):
        apify_data = {"musicMeta": {"musicId": ""}}
        result = _map_apify_to_update(apify_data)
        assert result["music_id"] is None

    def test_images_present_but_image_post_false(self):
        """If imagePost is falsy but images list has >1 items, still detect slideshow."""
        apify_data = {
            "imagePost": False,
            "images": ["https://img1.jpg", "https://img2.jpg"],
        }
        result = _map_apify_to_update(apify_data)
        # The logic is: is_slideshow or len(images) > 0 triggers non-video type
        # Since len(images) > 1 -> slideshow
        assert result["media_type"] == "slideshow"
        assert result["is_slideshow"] is False  # imagePost was False
        assert result["image_count"] == 2


# ==========================================================================
# 6. _get_engine
# ==========================================================================


class TestGetEngine:
    def test_normalizes_asyncpg_url(self):
        """_get_engine should replace postgresql+asyncpg:// with postgresql://."""
        import app.services.pipeline as handler_module

        # Reset cached engine
        handler_module._engine = None
        original_db_url = handler_module.DATABASE_URL

        try:
            handler_module.DATABASE_URL = "postgresql+asyncpg://user:pass@host/db"
            with patch.object(handler_module, "create_engine") as mock_create:
                mock_create.return_value = MagicMock()
                engine = _get_engine()
                mock_create.assert_called_once_with(
                    "postgresql://user:pass@host/db",
                    pool_pre_ping=True,
                    pool_size=1,
                    max_overflow=0,
                )
                assert engine is mock_create.return_value
        finally:
            handler_module.DATABASE_URL = original_db_url
            handler_module._engine = None

    def test_caches_engine_on_second_call(self):
        """_get_engine should return the same cached engine on subsequent calls."""
        import app.services.pipeline as handler_module

        handler_module._engine = None
        original_db_url = handler_module.DATABASE_URL

        try:
            handler_module.DATABASE_URL = "postgresql://user:pass@host/db"
            with patch.object(handler_module, "create_engine") as mock_create:
                sentinel = MagicMock()
                mock_create.return_value = sentinel

                first = _get_engine()
                second = _get_engine()

                assert first is second
                mock_create.assert_called_once()  # Only created once
        finally:
            handler_module.DATABASE_URL = original_db_url
            handler_module._engine = None

    def test_no_change_for_plain_postgresql_url(self):
        """Standard postgresql:// URL should pass through unchanged."""
        import app.services.pipeline as handler_module

        handler_module._engine = None
        original_db_url = handler_module.DATABASE_URL

        try:
            handler_module.DATABASE_URL = "postgresql://user:pass@host/db"
            with patch.object(handler_module, "create_engine") as mock_create:
                mock_create.return_value = MagicMock()
                _get_engine()
                mock_create.assert_called_once_with(
                    "postgresql://user:pass@host/db",
                    pool_pre_ping=True,
                    pool_size=1,
                    max_overflow=0,
                )
        finally:
            handler_module.DATABASE_URL = original_db_url
            handler_module._engine = None


# ==========================================================================
# 7. handler (entry point - empty Records case only)
# ==========================================================================


class TestHandler:
    def test_empty_records_returns_200(self):
        result = handler({"Records": []}, None)
        assert result == {"statusCode": 200, "body": "No records"}

    def test_missing_records_key_returns_200(self):
        result = handler({}, None)
        assert result == {"statusCode": 200, "body": "No records"}

    def test_no_records_with_context_object(self):
        """Handler should handle a context object without error for empty records."""
        mock_context = SimpleNamespace(aws_request_id="test-req-id")
        result = handler({"Records": []}, mock_context)
        assert result == {"statusCode": 200, "body": "No records"}
