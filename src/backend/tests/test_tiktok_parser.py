"""Tests for the TikTok export parser.

This module contains comprehensive tests for the TikTok parser including:
- Happy path scenarios
- Edge cases (empty exports, missing fields, malformed data)
- Security tests (zip-slip, path traversal)
- Forward compatibility tests (extra fields ignored)
"""

import io
import json
import os
import zipfile
from datetime import datetime
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

from app.schemas.tiktok_export import (
    EmptyExportError,
    InvalidExportError,
    TikTokExportSummary,
    TikTokParsedExport,
    TikTokVideoReference,
    ZipSecurityError,
)
from app.services.tiktok_parser import (
    get_export_summary,
    parse_tiktok_export,
)

# Test fixtures directory
FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "tests" / "fixtures" / "tiktok-exports"


def create_test_zip(files: dict[str, str | bytes]) -> io.BytesIO:
    """Create an in-memory ZIP file with the given files.

    Args:
        files: Dictionary mapping file paths to their content (str for JSON, bytes for binary)

    Returns:
        BytesIO object containing the ZIP file
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            if isinstance(content, str):
                zf.writestr(path, content)
            else:
                zf.writestr(path, content)
    buffer.seek(0)
    return buffer


def create_minimal_liked_export(videos: list[dict]) -> io.BytesIO:
    """Create a minimal ZIP with only liked videos.

    Args:
        videos: List of video dicts with 'date' and 'link' keys

    Returns:
        BytesIO object containing the ZIP file
    """
    data = {"Like List": {"ItemFavoriteList": videos}}
    return create_test_zip({"Activity/Like List.json": json.dumps(data)})


def create_minimal_favorited_export(videos: list[dict]) -> io.BytesIO:
    """Create a minimal ZIP with only favorited videos.

    Args:
        videos: List of video dicts with 'Date' and 'Link' keys

    Returns:
        BytesIO object containing the ZIP file
    """
    data = {"Favorite Videos": {"FavoriteVideoList": videos}}
    return create_test_zip({"Activity/Favorite Videos.json": json.dumps(data)})


def create_combined_export(liked_videos: list[dict], favorited_videos: list[dict]) -> io.BytesIO:
    """Create a combined single-file export.

    Args:
        liked_videos: List of liked video dicts
        favorited_videos: List of favorited video dicts

    Returns:
        BytesIO object containing the ZIP file
    """
    data = {
        "Likes and Favorites": {
            "Like List": {"ItemFavoriteList": liked_videos},
            "Favorite Videos": {"FavoriteVideoList": favorited_videos},
        }
    }
    return create_test_zip({"user_data.json": json.dumps(data)})


class TestParseExportHappyPath:
    """Tests for successful parsing scenarios."""

    def test_parse_export_liked_only_returns_data(self):
        """Test parsing an export with only liked videos."""
        videos = [
            {"date": "2025-10-02 16:37:01", "link": "https://www.tiktokv.com/share/video/123/"},
            {"date": "2025-10-02 16:33:15", "link": "https://www.tiktokv.com/share/video/456/"},
        ]
        zip_file = create_minimal_liked_export(videos)

        result = parse_tiktok_export(zip_file, scope="liked")

        assert isinstance(result, TikTokParsedExport)
        assert len(result.liked_videos) == 2
        assert len(result.favorited_videos) == 0
        assert result.summary.liked_count == 2
        assert result.summary.has_liked is True
        assert result.summary.has_favorited is False

    def test_parse_export_favorited_only_returns_data(self):
        """Test parsing an export with only favorited videos."""
        videos = [
            {"Date": "2025-10-02 04:28:00", "Link": "https://www.tiktokv.com/share/video/789/"},
            {"Date": "2025-10-02 03:59:42", "Link": "https://www.tiktokv.com/share/video/101/"},
        ]
        zip_file = create_minimal_favorited_export(videos)

        result = parse_tiktok_export(zip_file, scope="favorited")

        assert isinstance(result, TikTokParsedExport)
        assert len(result.liked_videos) == 0
        assert len(result.favorited_videos) == 2
        assert result.summary.favorited_count == 2
        assert result.summary.has_liked is False
        assert result.summary.has_favorited is True

    def test_parse_export_both_scope_returns_all(self):
        """Test parsing an export with both liked and favorited videos."""
        liked = [{"date": "2025-01-01 12:00:00", "link": "https://example.com/v1"}]
        favorited = [{"Date": "2025-01-02 12:00:00", "Link": "https://example.com/v2"}]

        zip_file = create_combined_export(liked, favorited)

        result = parse_tiktok_export(zip_file, scope="both")

        assert len(result.liked_videos) == 1
        assert len(result.favorited_videos) == 1
        assert result.summary.total_count == 2

    def test_parse_export_liked_only_scope_filters_favorited(self):
        """Test that liked scope only returns liked videos."""
        liked = [{"date": "2025-01-01 12:00:00", "link": "https://example.com/v1"}]
        favorited = [{"Date": "2025-01-02 12:00:00", "Link": "https://example.com/v2"}]

        zip_file = create_combined_export(liked, favorited)

        result = parse_tiktok_export(zip_file, scope="liked")

        assert len(result.liked_videos) == 1
        assert len(result.favorited_videos) == 0

    def test_parse_export_favorited_only_scope_filters_liked(self):
        """Test that favorited scope only returns favorited videos."""
        liked = [{"date": "2025-01-01 12:00:00", "link": "https://example.com/v1"}]
        favorited = [{"Date": "2025-01-02 12:00:00", "Link": "https://example.com/v2"}]

        zip_file = create_combined_export(liked, favorited)

        result = parse_tiktok_export(zip_file, scope="favorited")

        assert len(result.liked_videos) == 0
        assert len(result.favorited_videos) == 1

    def test_parse_export_video_reference_fields(self):
        """Test that video references have correct field values."""
        videos = [
            {"date": "2025-10-02 16:37:01", "link": "https://www.tiktokv.com/share/video/123/"},
        ]
        zip_file = create_minimal_liked_export(videos)

        result = parse_tiktok_export(zip_file, scope="liked")

        video = result.liked_videos[0]
        assert isinstance(video, TikTokVideoReference)
        assert video.url == "https://www.tiktokv.com/share/video/123/"
        assert video.interaction_type == "liked"
        assert isinstance(video.timestamp, datetime)
        assert video.timestamp.year == 2025
        assert video.timestamp.month == 10
        assert video.timestamp.day == 2

    def test_parse_export_unique_url_count(self):
        """Test that total_count reflects unique URLs across both lists."""
        # Same URL in both liked and favorited
        shared_url = "https://example.com/shared"
        liked = [
            {"date": "2025-01-01 12:00:00", "link": shared_url},
            {"date": "2025-01-02 12:00:00", "link": "https://example.com/liked_only"},
        ]
        favorited = [
            {"Date": "2025-01-03 12:00:00", "Link": shared_url},
            {"Date": "2025-01-04 12:00:00", "Link": "https://example.com/fav_only"},
        ]

        zip_file = create_combined_export(liked, favorited)

        result = parse_tiktok_export(zip_file, scope="both")

        assert result.summary.liked_count == 2
        assert result.summary.favorited_count == 2
        # Unique URLs: shared, liked_only, fav_only = 3
        assert result.summary.total_count == 3


class TestParseExportEdgeCases:
    """Tests for edge cases and unusual inputs."""

    def test_parse_export_empty_liked_list_returns_empty(self):
        """Test parsing an export with empty liked array."""
        data = {"Like List": {"ItemFavoriteList": []}}
        zip_file = create_test_zip(
            {
                "Activity/Like List.json": json.dumps(data),
                "Activity/Favorite Videos.json": json.dumps(
                    {
                        "Favorite Videos": {
                            "FavoriteVideoList": [
                                {"Date": "2025-01-01", "Link": "https://example.com/v1"}
                            ]
                        }
                    }
                ),
            }
        )

        result = parse_tiktok_export(zip_file, scope="both")

        assert len(result.liked_videos) == 0
        assert len(result.favorited_videos) == 1

    def test_parse_export_null_list_returns_empty(self):
        """Test parsing when the video list is null."""
        data = {"Like List": {"ItemFavoriteList": None}}
        zip_file = create_test_zip(
            {
                "Activity/Like List.json": json.dumps(data),
                "Activity/Favorite Videos.json": json.dumps(
                    {
                        "Favorite Videos": {
                            "FavoriteVideoList": [
                                {"Date": "2025-01-01", "Link": "https://example.com/v1"}
                            ]
                        }
                    }
                ),
            }
        )

        result = parse_tiktok_export(zip_file, scope="both")

        assert len(result.liked_videos) == 0
        assert len(result.favorited_videos) == 1

    def test_parse_export_missing_date_uses_fallback(self):
        """Test that videos without dates still parse with fallback timestamp."""
        videos = [
            {"link": "https://example.com/v1"},  # No date
        ]
        zip_file = create_minimal_liked_export(videos)

        result = parse_tiktok_export(zip_file, scope="liked")

        assert len(result.liked_videos) == 1
        # Should have a timestamp (fallback to current time)
        assert result.liked_videos[0].timestamp is not None

    def test_parse_export_missing_url_skips_entry(self):
        """Test that entries without URLs are skipped."""
        videos = [
            {"date": "2025-01-01 12:00:00"},  # No link
            {"date": "2025-01-02 12:00:00", "link": "https://example.com/v1"},
        ]
        zip_file = create_minimal_liked_export(videos)

        result = parse_tiktok_export(zip_file, scope="liked")

        assert len(result.liked_videos) == 1
        assert result.liked_videos[0].url == "https://example.com/v1"

    def test_parse_export_null_url_skips_entry(self):
        """Test that entries with null URLs are skipped."""
        videos = [
            {"date": "2025-01-01 12:00:00", "link": None},
            {"date": "2025-01-02 12:00:00", "link": "https://example.com/v1"},
        ]
        zip_file = create_minimal_liked_export(videos)

        result = parse_tiktok_export(zip_file, scope="liked")

        assert len(result.liked_videos) == 1

    def test_parse_export_extra_fields_ignored(self):
        """Test forward compatibility - extra fields are ignored."""
        videos = [
            {
                "date": "2025-01-01 12:00:00",
                "link": "https://example.com/v1",
                "engagement_score": 0.95,
                "ai_category": "entertainment",
                "unknown_field": {"nested": "data"},
            }
        ]
        zip_file = create_minimal_liked_export(videos)

        result = parse_tiktok_export(zip_file, scope="liked")

        assert len(result.liked_videos) == 1
        assert result.liked_videos[0].url == "https://example.com/v1"

    def test_parse_export_alternative_key_names(self):
        """Test parsing with alternative key names (capitalization variants)."""
        # Test with uppercase Date and Link
        data = {
            "Like List": {
                "ItemFavoriteList": [
                    {"Date": "2025-01-01 12:00:00", "Link": "https://example.com/v1"},
                ]
            }
        }
        zip_file = create_test_zip({"Activity/Like List.json": json.dumps(data)})

        result = parse_tiktok_export(zip_file, scope="liked")

        assert len(result.liked_videos) == 1

    def test_parse_export_date_only_format(self):
        """Test parsing dates without time component."""
        videos = [
            {"date": "2025-01-01", "link": "https://example.com/v1"},
        ]
        zip_file = create_minimal_liked_export(videos)

        result = parse_tiktok_export(zip_file, scope="liked")

        assert len(result.liked_videos) == 1
        assert result.liked_videos[0].timestamp.year == 2025
        assert result.liked_videos[0].timestamp.month == 1
        assert result.liked_videos[0].timestamp.day == 1


class TestParseExportErrors:
    """Tests for error scenarios."""

    def test_parse_export_both_empty_raises_error(self):
        """Test that EmptyExportError is raised when scope has no videos."""
        data = {"Like List": {"ItemFavoriteList": []}, "Favorite Videos": {"FavoriteVideoList": []}}
        zip_file = create_test_zip(
            {
                "Activity/Like List.json": json.dumps({"Like List": data["Like List"]}),
                "Activity/Favorite Videos.json": json.dumps(
                    {"Favorite Videos": data["Favorite Videos"]}
                ),
            }
        )

        with pytest.raises(EmptyExportError) as exc_info:
            parse_tiktok_export(zip_file, scope="both")

        assert exc_info.value.code == "EMPTY_EXPORT"

    def test_parse_export_missing_data_files_raises_error(self):
        """Test that InvalidExportError is raised when data files are missing."""
        # Create a ZIP with unrelated files
        zip_file = create_test_zip(
            {
                "README.txt": "This is not a TikTok export",
                "some_data.json": json.dumps({"foo": "bar"}),
            }
        )

        with pytest.raises(InvalidExportError) as exc_info:
            parse_tiktok_export(zip_file, scope="both")

        assert exc_info.value.code == "INVALID_EXPORT"

    def test_parse_export_invalid_json_raises_error(self):
        """Test that InvalidExportError is raised for malformed JSON."""
        zip_file = create_test_zip(
            {
                "Activity/Like List.json": "not valid json {{{",
            }
        )

        with pytest.raises(InvalidExportError) as exc_info:
            parse_tiktok_export(zip_file, scope="liked")

        assert exc_info.value.code == "INVALID_EXPORT"
        msg_lower = exc_info.value.message.lower()
        assert "json" in msg_lower or "malformed" in msg_lower

    def test_parse_export_not_a_zip_raises_error(self):
        """Test that InvalidExportError is raised for non-ZIP files."""
        not_a_zip = io.BytesIO(b"This is not a ZIP file")

        with pytest.raises(InvalidExportError) as exc_info:
            parse_tiktok_export(not_a_zip, scope="both")

        assert exc_info.value.code == "INVALID_EXPORT"


class TestZipSecurity:
    """Tests for ZIP security measures."""

    def test_parse_export_path_traversal_blocked(self):
        """Test that path traversal attacks are blocked."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            # Attempt to write outside extraction directory
            zf.writestr("../../../etc/passwd", "malicious content")
        buffer.seek(0)

        with pytest.raises(ZipSecurityError) as exc_info:
            parse_tiktok_export(buffer, scope="both")

        assert exc_info.value.code == "ZIP_SECURITY_ERROR"

    def test_parse_export_absolute_path_blocked(self):
        """Test that absolute paths are blocked."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("/etc/passwd", "malicious content")
        buffer.seek(0)

        with pytest.raises(ZipSecurityError) as exc_info:
            parse_tiktok_export(buffer, scope="both")

        assert exc_info.value.code == "ZIP_SECURITY_ERROR"

    def test_parse_export_double_dot_path_blocked(self):
        """Test that .. in paths is blocked."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("Activity/../../../etc/passwd", "malicious content")
        buffer.seek(0)

        with pytest.raises(ZipSecurityError) as exc_info:
            parse_tiktok_export(buffer, scope="both")

        assert exc_info.value.code == "ZIP_SECURITY_ERROR"


class TestGetExportSummary:
    """Tests for the get_export_summary function."""

    def test_get_summary_returns_counts(self):
        """Test that get_export_summary returns correct counts."""
        liked = [
            {"date": "2025-01-01 12:00:00", "link": "https://example.com/v1"},
            {"date": "2025-01-02 12:00:00", "link": "https://example.com/v2"},
        ]
        favorited = [
            {"Date": "2025-01-03 12:00:00", "Link": "https://example.com/v3"},
        ]

        zip_file = create_combined_export(liked, favorited)

        summary = get_export_summary(zip_file)

        assert isinstance(summary, TikTokExportSummary)
        assert summary.liked_count == 2
        assert summary.favorited_count == 1
        assert summary.total_count == 3
        assert summary.has_liked is True
        assert summary.has_favorited is True

    def test_get_summary_with_empty_favorited(self):
        """Test summary when only liked videos exist."""
        videos = [
            {"date": "2025-01-01 12:00:00", "link": "https://example.com/v1"},
        ]
        zip_file = create_minimal_liked_export(videos)

        summary = get_export_summary(zip_file)

        assert summary.liked_count == 1
        assert summary.favorited_count == 0
        assert summary.has_liked is True
        assert summary.has_favorited is False


class TestParseErrorModels:
    """Tests for error model serialization."""

    def test_error_to_parse_error_conversion(self):
        """Test that exceptions can be converted to ParseError models."""
        error = InvalidExportError("Custom error message", details={"key": "value"})

        parse_error = error.to_parse_error()

        assert parse_error.code == "INVALID_EXPORT"
        assert parse_error.message == "Custom error message"
        assert parse_error.details == {"key": "value"}

    def test_empty_export_error_conversion(self):
        """Test EmptyExportError conversion."""
        error = EmptyExportError("No videos found", details={"scope": "liked"})

        parse_error = error.to_parse_error()

        assert parse_error.code == "EMPTY_EXPORT"
        assert "No videos" in parse_error.message

    def test_zip_security_error_conversion(self):
        """Test ZipSecurityError conversion."""
        error = ZipSecurityError("Path traversal detected", details={"path": "../etc/passwd"})

        parse_error = error.to_parse_error()

        assert parse_error.code == "ZIP_SECURITY_ERROR"


class TestWithRealFixtures:
    """Tests using real anonymized fixture files."""

    @pytest.mark.skipif(
        not (FIXTURES_DIR / "slices" / "minimal.json").exists(), reason="Fixture file not found"
    )
    def test_parse_minimal_fixture(self):
        """Test parsing the minimal fixture file.

        This test uses a real fixture if available.
        """
        # The fixture is a JSON file, need to wrap in ZIP
        fixture_path = FIXTURES_DIR / "slices" / "minimal.json"

        with open(fixture_path) as f:
            data = json.load(f)

        # Create a combined export from the fixture
        zip_file = create_test_zip({"user_data.json": json.dumps(data)})

        # This should parse without errors (may be empty depending on fixture)
        try:
            result = parse_tiktok_export(zip_file, scope="both")
            assert isinstance(result, TikTokParsedExport)
        except EmptyExportError:
            # If the fixture has no videos, that's also acceptable
            pass

    @pytest.mark.skipif(
        not (FIXTURES_DIR / "edge_cases" / "extra_fields.json").exists(),
        reason="Fixture file not found",
    )
    def test_parse_extra_fields_fixture(self):
        """Test that extra fields in fixture are ignored."""
        fixture_path = FIXTURES_DIR / "edge_cases" / "extra_fields.json"

        with open(fixture_path) as f:
            data = json.load(f)

        zip_file = create_test_zip({"user_data.json": json.dumps(data)})

        try:
            result = parse_tiktok_export(zip_file, scope="both")
            assert isinstance(result, TikTokParsedExport)
        except EmptyExportError:
            pass


class TestFilePathInput:
    """Tests for file path input handling."""

    def test_parse_from_path(self, tmp_path):
        """Test parsing from a file path instead of BytesIO."""
        videos = [
            {"date": "2025-01-01 12:00:00", "link": "https://example.com/v1"},
        ]

        # Create a real ZIP file
        zip_path = tmp_path / "test_export.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            data = {"Like List": {"ItemFavoriteList": videos}}
            zf.writestr("Activity/Like List.json", json.dumps(data))

        # Parse from path
        result = parse_tiktok_export(zip_path, scope="liked")

        assert len(result.liked_videos) == 1
        assert result.liked_videos[0].url == "https://example.com/v1"
