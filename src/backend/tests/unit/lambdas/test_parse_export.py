"""
Tests for Parse Export Lambda.

Task: 3.2
Spec: docs/MVP/tasks/specs/3-3.2.md
"""

import io
import json
import os
import zipfile
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

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

# TODO: Import the Lambda handler once implemented
# from lambdas.parse_export.handler import handler, parse_export_zip, create_media_events


# Test fixtures

@pytest.fixture
def mock_upload_id() -> UUID:
    """Generate a test upload ID."""
    return uuid4()


@pytest.fixture
def mock_user_id() -> UUID:
    """Generate a test user ID."""
    return uuid4()


@pytest.fixture
def mock_execution_arn() -> str:
    """Generate a test Step Functions execution ARN."""
    return "arn:aws:states:us-east-1:123456789:execution:attic-pipeline:test-exec-123"


@pytest.fixture
def parse_export_input(mock_upload_id: UUID, mock_user_id: UUID, mock_execution_arn: str) -> dict:
    """Create a valid ParseExportInput event."""
    return {
        "upload_id": str(mock_upload_id),
        "user_id": str(mock_user_id),
        "storage_path": f"uploads/{mock_user_id}/{mock_upload_id}/export.zip",
        "scope": "liked",
        "execution_arn": mock_execution_arn,
    }


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
    """Create a combined export with both liked and favorited videos.

    Args:
        liked_videos: List of liked video dicts
        favorited_videos: List of favorited video dicts

    Returns:
        BytesIO object containing the ZIP file
    """
    liked_data = {"Like List": {"ItemFavoriteList": liked_videos}}
    favorited_data = {"Favorite Videos": {"FavoriteVideoList": favorited_videos}}
    return create_test_zip({
        "Activity/Like List.json": json.dumps(liked_data),
        "Activity/Favorite Videos.json": json.dumps(favorited_data),
    })


class TestParseExportHappyPath:
    """Tests for successful parsing scenarios."""

    @pytest.mark.asyncio
    async def test_parse_export_valid_zip_extracts_urls(self, parse_export_input: dict):
        """Test that parse_export extracts URLs from valid ZIP file."""
        # Arrange
        # TODO: Mock Supabase Storage download to return test ZIP
        # TODO: Mock database session for media_event creation

        # Act
        # TODO: Call handler(parse_export_input, mock_context)

        # Assert
        # TODO: Verify output contains media_items list
        # TODO: Verify total_items matches expected count
        # TODO: Verify each media_item has required fields (media_event_id, platform_id, canonical_url, interaction_type, media_type)
        pytest.skip("Test stub - implement during task 3.2")

    @pytest.mark.asyncio
    async def test_parse_export_liked_only_scope_filters_correctly(self, parse_export_input: dict):
        """Test that liked scope only returns liked videos."""
        # Arrange
        # TODO: Create combined export with both liked and favorited
        # TODO: Mock storage to return combined export
        # TODO: Set scope to "liked" in input

        # Act
        # TODO: Call handler

        # Assert
        # TODO: Verify output contains only liked videos
        # TODO: Verify liked_count > 0
        # TODO: Verify favorited_count == 0
        pytest.skip("Test stub - implement during task 3.2")

    @pytest.mark.asyncio
    async def test_parse_export_favorited_only_scope_filters_correctly(self, parse_export_input: dict):
        """Test that favorited scope only returns favorited videos."""
        # Arrange
        # TODO: Create combined export with both liked and favorited
        # TODO: Mock storage to return combined export
        # TODO: Set scope to "favorited" in input

        # Act
        # TODO: Call handler

        # Assert
        # TODO: Verify output contains only favorited videos
        # TODO: Verify favorited_count > 0
        # TODO: Verify liked_count == 0
        pytest.skip("Test stub - implement during task 3.2")

    @pytest.mark.asyncio
    async def test_parse_export_both_scope_includes_all(self, parse_export_input: dict):
        """Test that both scope includes all videos."""
        # Arrange
        # TODO: Create combined export with both liked and favorited
        # TODO: Mock storage to return combined export
        # TODO: Set scope to "both" in input

        # Act
        # TODO: Call handler

        # Assert
        # TODO: Verify output contains both liked and favorited videos
        # TODO: Verify total_items == liked_count + favorited_count
        pytest.skip("Test stub - implement during task 3.2")


class TestParseExportErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_parse_export_missing_like_list_raises_error(self, parse_export_input: dict):
        """Test that missing Like List.json raises error when scope is liked."""
        # Arrange
        # TODO: Create ZIP without Like List.json
        # TODO: Mock storage to return invalid ZIP
        # TODO: Set scope to "liked" in input

        # Act & Assert
        # TODO: Verify handler raises appropriate exception with clear error message
        pytest.skip("Test stub - implement during task 3.2")

    @pytest.mark.asyncio
    async def test_parse_export_empty_export_returns_zero_items(self, parse_export_input: dict):
        """Test that empty export returns zero items gracefully."""
        # Arrange
        # TODO: Create ZIP with empty Like List
        # TODO: Mock storage to return empty ZIP

        # Act
        # TODO: Call handler

        # Assert
        # TODO: Verify total_items == 0
        # TODO: Verify media_items is empty list
        # TODO: Verify liked_count == 0
        # TODO: Verify favorited_count == 0
        pytest.skip("Test stub - implement during task 3.2")


class TestParseExportIdempotency:
    """Tests for idempotent behavior."""

    @pytest.mark.asyncio
    async def test_parse_export_deterministic_ids_on_retry(self, parse_export_input: dict):
        """Test that media_event IDs are deterministic on retry."""
        # Arrange
        # TODO: Create test ZIP with videos
        # TODO: Mock storage to return same ZIP
        # TODO: Call handler twice with same input

        # Act
        # TODO: result1 = handler(parse_export_input, context)
        # TODO: result2 = handler(parse_export_input, context)

        # Assert
        # TODO: Verify result1.media_items[0].media_event_id == result2.media_items[0].media_event_id
        # TODO: Verify IDs are generated using uuid5(user_id:platform:platform_id)
        pytest.skip("Test stub - implement during task 3.2")


class TestParseExportMediaTypeDetection:
    """Tests for media type detection."""

    @pytest.mark.asyncio
    async def test_parse_export_detects_slideshow_media_type(self, parse_export_input: dict):
        """Test that slideshow media type is detected correctly."""
        # Arrange
        # TODO: Create test data with slideshow (multiple images)
        # TODO: Mock storage to return slideshow data

        # Act
        # TODO: Call handler

        # Assert
        # TODO: Verify media_type == "slideshow" for slideshow items
        # TODO: Verify image_count > 1 for slideshow
        pytest.skip("Test stub - implement during task 3.2")

    @pytest.mark.asyncio
    async def test_parse_export_detects_video_media_type(self, parse_export_input: dict):
        """Test that video media type is detected correctly."""
        # Arrange
        # TODO: Create test data with standard video URLs
        # TODO: Mock storage to return video data

        # Act
        # TODO: Call handler

        # Assert
        # TODO: Verify media_type == "video" for video items
        pytest.skip("Test stub - implement during task 3.2")

    @pytest.mark.asyncio
    async def test_parse_export_detects_image_media_type(self, parse_export_input: dict):
        """Test that single image media type is detected correctly."""
        # Arrange
        # TODO: Create test data with single image
        # TODO: Mock storage to return image data

        # Act
        # TODO: Call handler

        # Assert
        # TODO: Verify media_type == "image" for single image items
        pytest.skip("Test stub - implement during task 3.2")


class TestParseExportOutput:
    """Tests for output format validation."""

    @pytest.mark.asyncio
    async def test_parse_export_output_matches_schema(self, parse_export_input: dict):
        """Test that output matches ParseExportOutput schema."""
        # Arrange
        # TODO: Create valid test ZIP
        # TODO: Mock storage and database

        # Act
        # TODO: result = handler(parse_export_input, context)

        # Assert
        # TODO: Verify result has upload_id field
        # TODO: Verify result has total_items field
        # TODO: Verify result has media_items list
        # TODO: Verify result has liked_count field
        # TODO: Verify result has favorited_count field
        # TODO: Verify each media_item matches MediaItem schema
        pytest.skip("Test stub - implement during task 3.2")

    @pytest.mark.asyncio
    async def test_parse_export_media_item_has_required_fields(self, parse_export_input: dict):
        """Test that each MediaItem has all required fields."""
        # Arrange
        # TODO: Create valid test ZIP
        # TODO: Mock storage and database

        # Act
        # TODO: result = handler(parse_export_input, context)

        # Assert
        # TODO: For each media_item, verify:
        # TODO:   - media_event_id is UUID
        # TODO:   - platform_id is string
        # TODO:   - canonical_url is valid URL
        # TODO:   - interaction_type in ["liked", "favorited"]
        # TODO:   - media_type in ["video", "image", "slideshow"]
        pytest.skip("Test stub - implement during task 3.2")


class TestParseExportLogging:
    """Tests for observability and logging."""

    @pytest.mark.asyncio
    async def test_parse_export_logs_correlation_fields(self, parse_export_input: dict):
        """Test that handler logs required correlation fields."""
        # Arrange
        # TODO: Create valid test ZIP
        # TODO: Mock logger to capture log calls

        # Act
        # TODO: Call handler

        # Assert
        # TODO: Verify logs contain upload_id
        # TODO: Verify logs contain user_id
        # TODO: Verify logs contain execution_arn
        # TODO: Verify logs contain step_name: "PARSE_EXPORT"
        pytest.skip("Test stub - implement during task 3.2")

    @pytest.mark.asyncio
    async def test_parse_export_logs_metrics(self, parse_export_input: dict):
        """Test that handler logs metrics."""
        # Arrange
        # TODO: Create valid test ZIP
        # TODO: Mock logger to capture log calls

        # Act
        # TODO: Call handler

        # Assert
        # TODO: Verify logs contain total_items
        # TODO: Verify logs contain liked_count
        # TODO: Verify logs contain favorited_count
        # TODO: Verify logs contain duration_ms
        # TODO: Verify logs contain zip_size_bytes
        pytest.skip("Test stub - implement during task 3.2")
