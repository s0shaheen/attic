"""Tests for the Instagram export parser.

Covers:
- Happy path parsing of saved posts and collections
- Platform ID extraction from URL patterns (/p/, /reel/, /tv/)
- Collection sequential parsing (header/item structure)
- Edge cases (empty exports, missing fields, missing collections file)
- Security tests (zip-slip, path traversal)
"""

import io
import json
import os
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

# Set test environment variables before importing app modules
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("SUPABASE_URL", "https://test-project.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-for-testing-only")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test-aws-key")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test-aws-secret")
os.environ.setdefault("APIFY_API_TOKEN", "test-apify-token")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("STRIPE_SECRET_KEY", "test-stripe-key")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "test-stripe-webhook")
os.environ.setdefault("RESEND_API_KEY", "test-resend-key")

from app.schemas.instagram_export import (
    EmptyExportError,
    InstagramParsedExport,
    InstagramPostReference,
    InvalidExportError,
    ZipSecurityError,
    extract_shortcode,
    infer_media_hint,
)
from app.services.instagram_parser import (
    get_export_summary,
    parse_instagram_export,
)

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _create_test_zip(files: dict[str, str]) -> io.BytesIO:
    """Create an in-memory ZIP file with given file paths and JSON content."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    buffer.seek(0)
    return buffer


def _make_saved_posts(items: list[dict]) -> str:
    """Build saved_posts.json content from a list of raw items."""
    return json.dumps({"saved_saved_media": items})


def _make_saved_post_item(
    url: str = "https://www.instagram.com/reel/ABC123/",
    creator: str = "testuser",
    timestamp: int = 1700000000,
) -> dict:
    """Create a single saved post item in IG export format."""
    return {
        "title": creator,
        "string_map_data": {
            "Saved on": {"href": url, "timestamp": timestamp},
        },
    }


def _make_collections(entries: list[dict]) -> str:
    """Build saved_collections.json content from raw entries."""
    return json.dumps({"saved_saved_collections": entries})


def _make_collection_header(
    name: str, created_ts: int = 1700000000, updated_ts: int = 1700000000
) -> dict:
    """Create a collection header entry."""
    return {
        "title": "Collection",
        "string_map_data": {
            "Name": {"value": name},
            "Creation Time": {"timestamp": created_ts},
            "Update Time": {"timestamp": updated_ts},
        },
    }


def _make_collection_item(
    url: str = "https://www.instagram.com/reel/ABC123/",
    creator: str = "testuser",
    added_ts: int = 1700000000,
) -> dict:
    """Create a collection item entry."""
    return {
        "string_map_data": {
            "Name": {"href": url, "value": creator},
            "Added Time": {"timestamp": added_ts},
        },
    }


def _build_full_zip(
    saved_posts: list[dict] | None = None,
    collection_entries: list[dict] | None = None,
) -> io.BytesIO:
    """Build a ZIP with saved_posts.json and optionally saved_collections.json."""
    files: dict[str, str] = {}

    if saved_posts is not None:
        files["your_instagram_activity/saved/saved_posts.json"] = _make_saved_posts(saved_posts)

    if collection_entries is not None:
        files["your_instagram_activity/saved/saved_collections.json"] = _make_collections(
            collection_entries
        )

    return _create_test_zip(files)


# ---------------------------------------------------------------------------
# Schema unit tests
# ---------------------------------------------------------------------------


class TestExtractShortcode:
    def test_extract_from_post_url(self):
        assert extract_shortcode("https://www.instagram.com/p/CqwTnSTuWWJ/") == "CqwTnSTuWWJ"

    def test_extract_from_reel_url(self):
        assert extract_shortcode("https://www.instagram.com/reel/DVaDM79EwOV/") == "DVaDM79EwOV"

    def test_extract_from_tv_url(self):
        assert extract_shortcode("https://www.instagram.com/tv/CXyz123_ab/") == "CXyz123_ab"

    def test_extract_from_url_without_trailing_slash(self):
        assert extract_shortcode("https://www.instagram.com/p/ABC123") == "ABC123"

    def test_returns_none_for_invalid_url(self):
        assert extract_shortcode("https://www.instagram.com/username/") is None

    def test_returns_none_for_empty_string(self):
        assert extract_shortcode("") is None

    def test_handles_hyphen_and_underscore_in_shortcode(self):
        assert extract_shortcode("https://www.instagram.com/p/A-B_C/") == "A-B_C"


class TestInferMediaHint:
    def test_reel_url(self):
        assert infer_media_hint("https://www.instagram.com/reel/ABC/") == "reel"

    def test_igtv_url(self):
        assert infer_media_hint("https://www.instagram.com/tv/ABC/") == "igtv"

    def test_post_url(self):
        assert infer_media_hint("https://www.instagram.com/p/ABC/") == "post"

    def test_unknown_url_defaults_to_post(self):
        assert infer_media_hint("https://www.instagram.com/something/") == "post"


class TestInstagramPostReference:
    def test_computed_platform_id(self):
        post = InstagramPostReference(
            url="https://www.instagram.com/reel/DVaDM79EwOV/",
            timestamp=datetime(2025, 1, 1, tzinfo=UTC),
            creator_username="testuser",
        )
        assert post.platform_id == "DVaDM79EwOV"

    def test_computed_media_hint(self):
        post = InstagramPostReference(
            url="https://www.instagram.com/tv/ABC123/",
            timestamp=datetime(2025, 1, 1, tzinfo=UTC),
            creator_username="testuser",
        )
        assert post.media_hint == "igtv"


# ---------------------------------------------------------------------------
# Parser happy path
# ---------------------------------------------------------------------------


class TestParseInstagramExportHappyPath:
    def test_parse_saved_posts_returns_data(self):
        posts = [
            _make_saved_post_item("https://www.instagram.com/reel/AAA/", "user1", 1700000000),
            _make_saved_post_item("https://www.instagram.com/p/BBB/", "user2", 1700000001),
        ]
        zf = _build_full_zip(saved_posts=posts)

        result = parse_instagram_export(zf)

        assert isinstance(result, InstagramParsedExport)
        assert len(result.saved_posts) == 2
        assert result.summary.saved_count == 2

    def test_parse_saved_post_fields(self):
        posts = [
            _make_saved_post_item(
                "https://www.instagram.com/reel/DVaDM79EwOV/", "korkierey", 1774223235
            ),
        ]
        zf = _build_full_zip(saved_posts=posts)

        result = parse_instagram_export(zf)

        post = result.saved_posts[0]
        assert post.url == "https://www.instagram.com/reel/DVaDM79EwOV/"
        assert post.creator_username == "korkierey"
        assert post.platform_id == "DVaDM79EwOV"
        assert post.media_hint == "reel"
        assert isinstance(post.timestamp, datetime)

    def test_parse_with_collections(self):
        posts = [
            _make_saved_post_item("https://www.instagram.com/reel/AAA/", "user1"),
            _make_saved_post_item("https://www.instagram.com/p/BBB/", "user2"),
        ]
        collection_entries = [
            _make_collection_header("Food n recipes", 1710355922, 1725770652),
            _make_collection_item("https://www.instagram.com/reel/CCC/", "chef1", 1727979858),
            _make_collection_item("https://www.instagram.com/reel/DDD/", "chef2", 1725727076),
            _make_collection_header("Art", 1769190496, 1769190496),
            _make_collection_item("https://www.instagram.com/reel/EEE/", "artist1", 1769408899),
        ]
        zf = _build_full_zip(saved_posts=posts, collection_entries=collection_entries)

        result = parse_instagram_export(zf)

        assert result.summary.saved_count == 2
        assert result.summary.collection_count == 2
        assert result.summary.collection_names == ["Food n recipes", "Art"]
        assert len(result.collections[0].items) == 2
        assert len(result.collections[1].items) == 1

    def test_collection_item_fields(self):
        posts = [_make_saved_post_item()]
        collection_entries = [
            _make_collection_header("Test"),
            _make_collection_item(
                "https://www.instagram.com/p/CqwTnSTuWWJ/", "endbackpain", 1682137866
            ),
        ]
        zf = _build_full_zip(saved_posts=posts, collection_entries=collection_entries)

        result = parse_instagram_export(zf)

        item = result.collections[0].items[0]
        assert item.url == "https://www.instagram.com/p/CqwTnSTuWWJ/"
        assert item.creator_username == "endbackpain"
        assert item.platform_id == "CqwTnSTuWWJ"
        assert isinstance(item.added_at, datetime)

    def test_collection_header_fields(self):
        posts = [_make_saved_post_item()]
        collection_entries = [
            _make_collection_header("Food n recipes", 1710355922, 1725770652),
        ]
        zf = _build_full_zip(saved_posts=posts, collection_entries=collection_entries)

        result = parse_instagram_export(zf)

        coll = result.collections[0]
        assert coll.name == "Food n recipes"
        assert isinstance(coll.created_at, datetime)
        assert isinstance(coll.updated_at, datetime)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestParseInstagramExportEdgeCases:
    def test_missing_collections_file_still_parses(self):
        """Collections file is optional — not all users have collections."""
        posts = [_make_saved_post_item()]
        zf = _build_full_zip(saved_posts=posts, collection_entries=None)

        result = parse_instagram_export(zf)

        assert result.summary.saved_count == 1
        assert result.summary.collection_count == 0
        assert result.collections == []

    def test_empty_collections_array(self):
        posts = [_make_saved_post_item()]
        zf = _build_full_zip(saved_posts=posts, collection_entries=[])

        result = parse_instagram_export(zf)

        assert result.collections == []

    def test_collection_header_with_no_items(self):
        posts = [_make_saved_post_item()]
        collection_entries = [
            _make_collection_header("Empty Collection"),
        ]
        zf = _build_full_zip(saved_posts=posts, collection_entries=collection_entries)

        result = parse_instagram_export(zf)

        assert len(result.collections) == 1
        assert result.collections[0].name == "Empty Collection"
        assert result.collections[0].items == []

    def test_post_without_url_skipped(self):
        posts = [
            {"title": "nourl", "string_map_data": {"Saved on": {"timestamp": 1700000000}}},
            _make_saved_post_item("https://www.instagram.com/p/AAA/", "user1"),
        ]
        zf = _build_full_zip(saved_posts=posts)

        result = parse_instagram_export(zf)

        assert len(result.saved_posts) == 1
        assert result.saved_posts[0].creator_username == "user1"

    def test_post_with_empty_creator_title(self):
        posts = [
            {
                "string_map_data": {
                    "Saved on": {
                        "href": "https://www.instagram.com/p/AAA/",
                        "timestamp": 1700000000,
                    }
                }
            }
        ]
        zf = _build_full_zip(saved_posts=posts)

        result = parse_instagram_export(zf)

        assert len(result.saved_posts) == 1
        assert result.saved_posts[0].creator_username == ""

    def test_collection_item_without_url_skipped(self):
        posts = [_make_saved_post_item()]
        collection_entries = [
            _make_collection_header("Test"),
            {
                "string_map_data": {
                    "Name": {"value": "nourl"},
                    "Added Time": {"timestamp": 1700000000},
                }
            },
            _make_collection_item("https://www.instagram.com/p/AAA/", "user1"),
        ]
        zf = _build_full_zip(saved_posts=posts, collection_entries=collection_entries)

        result = parse_instagram_export(zf)

        assert len(result.collections[0].items) == 1

    def test_extra_fields_ignored(self):
        posts = [
            {
                "title": "user1",
                "extra_field": "ignored",
                "string_map_data": {
                    "Saved on": {
                        "href": "https://www.instagram.com/p/AAA/",
                        "timestamp": 1700000000,
                    },
                    "Extra Key": {"value": "ignored"},
                },
            }
        ]
        zf = _build_full_zip(saved_posts=posts)

        result = parse_instagram_export(zf)

        assert len(result.saved_posts) == 1

    def test_multiple_url_patterns(self):
        """Verify all three URL patterns parse correctly."""
        posts = [
            _make_saved_post_item("https://www.instagram.com/p/POST123/", "u1"),
            _make_saved_post_item("https://www.instagram.com/reel/REEL456/", "u2"),
            _make_saved_post_item("https://www.instagram.com/tv/TV789/", "u3"),
        ]
        zf = _build_full_zip(saved_posts=posts)

        result = parse_instagram_export(zf)

        assert len(result.saved_posts) == 3
        assert result.saved_posts[0].platform_id == "POST123"
        assert result.saved_posts[0].media_hint == "post"
        assert result.saved_posts[1].platform_id == "REEL456"
        assert result.saved_posts[1].media_hint == "reel"
        assert result.saved_posts[2].platform_id == "TV789"
        assert result.saved_posts[2].media_hint == "igtv"


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestParseInstagramExportErrors:
    def test_no_saved_files_at_all_raises_invalid(self):
        """ZIP with neither saved_posts.json nor saved_collections.json."""
        zf = _create_test_zip({"some_other_file.json": "{}"})

        with pytest.raises((InvalidExportError, EmptyExportError)):
            parse_instagram_export(zf)

    def test_empty_saved_posts_no_collections_raises_empty(self):
        zf = _build_full_zip(saved_posts=[], collection_entries=None)

        with pytest.raises(EmptyExportError) as exc_info:
            parse_instagram_export(zf)

        assert exc_info.value.code == "EMPTY_EXPORT"

    def test_empty_saved_posts_with_collections_extracts_from_collections(self):
        """Collections items become saved_posts when saved_posts array is empty."""
        collection_entries = [
            _make_collection_header("My Collection"),
            _make_collection_item("https://www.instagram.com/reel/AAA/", "user1"),
            _make_collection_item("https://www.instagram.com/p/BBB/", "user2"),
        ]
        zf = _build_full_zip(saved_posts=[], collection_entries=collection_entries)

        result = parse_instagram_export(zf)

        assert result.summary.saved_count == 2
        assert result.summary.collection_count == 1
        urls = {p.url for p in result.saved_posts}
        assert "https://www.instagram.com/reel/AAA/" in urls
        assert "https://www.instagram.com/p/BBB/" in urls

    def test_missing_saved_posts_file_with_collections_still_works(self):
        """Only saved_collections.json exists (no saved_posts.json)."""
        collection_entries = [
            _make_collection_header("Test"),
            _make_collection_item("https://www.instagram.com/p/CCC/", "user3"),
        ]
        zf = _create_test_zip(
            {
                "your_instagram_activity/saved/saved_collections.json": _make_collections(
                    collection_entries
                )
            }
        )

        result = parse_instagram_export(zf)

        assert result.summary.saved_count == 1
        assert result.summary.collection_count == 1

    def test_malformed_json_raises_invalid(self):
        zf = _create_test_zip({"your_instagram_activity/saved/saved_posts.json": "not json {{{"})

        with pytest.raises(InvalidExportError) as exc_info:
            parse_instagram_export(zf)

        msg = exc_info.value.message.lower()
        assert "json" in msg or "malformed" in msg

    def test_not_a_zip_raises_invalid(self):
        not_a_zip = io.BytesIO(b"This is not a ZIP file")

        with pytest.raises(InvalidExportError) as exc_info:
            parse_instagram_export(not_a_zip)

        assert exc_info.value.code == "INVALID_EXPORT"

    def test_saved_posts_wrong_key_no_collections_raises_empty(self):
        """saved_posts.json exists but has wrong key, no collections."""
        zf = _create_test_zip(
            {"your_instagram_activity/saved/saved_posts.json": json.dumps({"wrong_key": []})}
        )

        with pytest.raises(EmptyExportError):
            parse_instagram_export(zf)


# ---------------------------------------------------------------------------
# ZIP security
# ---------------------------------------------------------------------------


class TestInstagramZipSecurity:
    def test_path_traversal_blocked(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("../../../etc/passwd", "malicious")
        buffer.seek(0)

        with pytest.raises(ZipSecurityError):
            parse_instagram_export(buffer)

    def test_absolute_path_blocked(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("/etc/passwd", "malicious")
        buffer.seek(0)

        with pytest.raises(ZipSecurityError):
            parse_instagram_export(buffer)

    def test_double_dot_path_blocked(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("your_instagram_activity/../../../etc/passwd", "malicious")
        buffer.seek(0)

        with pytest.raises(ZipSecurityError):
            parse_instagram_export(buffer)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


class TestGetExportSummary:
    def test_summary_returns_counts(self):
        posts = [
            _make_saved_post_item("https://www.instagram.com/p/A/", "u1"),
            _make_saved_post_item("https://www.instagram.com/p/B/", "u2"),
        ]
        collection_entries = [
            _make_collection_header("Coll1"),
            _make_collection_item("https://www.instagram.com/p/C/", "u3"),
        ]
        zf = _build_full_zip(saved_posts=posts, collection_entries=collection_entries)

        summary = get_export_summary(zf)

        assert summary.saved_count == 2
        assert summary.collection_count == 1
        assert summary.collection_names == ["Coll1"]


# ---------------------------------------------------------------------------
# File path input
# ---------------------------------------------------------------------------


class TestFilePathInput:
    def test_parse_from_path(self, tmp_path):
        posts = [_make_saved_post_item()]
        zip_path = tmp_path / "test_export.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr(
                "your_instagram_activity/saved/saved_posts.json",
                _make_saved_posts(posts),
            )

        result = parse_instagram_export(zip_path)

        assert len(result.saved_posts) == 1


# ---------------------------------------------------------------------------
# Real export fixture (optional — runs only when fixture exists)
# ---------------------------------------------------------------------------

_REAL_FIXTURE = (
    Path(__file__).parent.parent.parent.parent
    / "workbench"
    / "data"
    / "instagram-export-sample.zip"
)


class TestParserEdgeCases:
    """Edge cases found by review agents."""

    def test_url_with_query_parameters(self):
        assert extract_shortcode("https://www.instagram.com/p/ABC123/?utm_source=ig") == "ABC123"

    def test_non_instagram_url_returns_none_shortcode(self):
        assert extract_shortcode("https://www.tiktok.com/@user/video/123") is None

    def test_string_map_data_missing_entirely(self):
        posts = [{"title": "user1"}]  # no string_map_data at all
        zf = _build_full_zip(saved_posts=posts)

        with pytest.raises(EmptyExportError):
            parse_instagram_export(zf)

    def test_timestamp_zero_returns_epoch(self):
        posts = [_make_saved_post_item(timestamp=0)]
        zf = _build_full_zip(saved_posts=posts)

        result = parse_instagram_export(zf)

        assert result.saved_posts[0].timestamp.year == 1970

    def test_orphaned_collection_items_before_header_skipped(self):
        """Items before first collection header are discarded."""
        collection_entries = [
            _make_collection_item("https://www.instagram.com/p/ORPHAN/", "orphan_user"),
            _make_collection_header("Real Collection"),
            _make_collection_item("https://www.instagram.com/p/REAL/", "real_user"),
        ]
        zf = _build_full_zip(
            saved_posts=[_make_saved_post_item()], collection_entries=collection_entries
        )

        result = parse_instagram_export(zf)

        assert len(result.collections) == 1
        assert result.collections[0].name == "Real Collection"
        assert len(result.collections[0].items) == 1
        assert result.collections[0].items[0].creator_username == "real_user"

    def test_duplicate_collection_names_creates_separate_objects(self):
        collection_entries = [
            _make_collection_header("Duped"),
            _make_collection_item("https://www.instagram.com/p/A/", "u1"),
            _make_collection_header("Duped"),
            _make_collection_item("https://www.instagram.com/p/B/", "u2"),
        ]
        zf = _build_full_zip(
            saved_posts=[_make_saved_post_item()], collection_entries=collection_entries
        )

        result = parse_instagram_export(zf)

        assert len(result.collections) == 2
        assert result.collections[0].name == "Duped"
        assert result.collections[1].name == "Duped"

    def test_collection_item_missing_added_time(self):
        collection_entries = [
            _make_collection_header("Test"),
            {
                "string_map_data": {
                    "Name": {
                        "href": "https://www.instagram.com/p/AAA/",
                        "value": "creator",
                    }
                }
            },
        ]
        zf = _build_full_zip(
            saved_posts=[_make_saved_post_item()], collection_entries=collection_entries
        )

        result = parse_instagram_export(zf)

        assert len(result.collections[0].items) == 1
        assert result.collections[0].items[0].added_at is not None


class TestWithRealFixture:
    @pytest.mark.skipif(not _REAL_FIXTURE.exists(), reason="Real IG export fixture not found")
    def test_parse_real_export(self):
        result = parse_instagram_export(_REAL_FIXTURE)

        # From our analysis: 1334 saved posts, 5 collections
        assert result.summary.saved_count == 1334
        assert result.summary.collection_count == 5
        assert "Food n recipes" in result.summary.collection_names
        assert "Art" in result.summary.collection_names

    @pytest.mark.skipif(not _REAL_FIXTURE.exists(), reason="Real IG export fixture not found")
    def test_real_export_url_patterns(self):
        result = parse_instagram_export(_REAL_FIXTURE)

        # All posts should have valid URLs and platform IDs
        for post in result.saved_posts:
            assert post.url.startswith("https://www.instagram.com/")
            assert post.platform_id is not None
            assert post.media_hint in ("post", "reel", "igtv")
