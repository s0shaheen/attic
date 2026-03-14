"""
Integration tests for Parse Export Lambda.

Task: 3.2
Spec: docs/MVP/tasks/specs/3-3.2.md
"""

import io
import json
import os
import zipfile
from uuid import UUID, uuid4

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

# TODO: Import the Lambda handler once implemented
# from lambdas.parse_export.handler import handler


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


@pytest.fixture
async def db_session():
    """Create a test database session.

    TODO: Set up test database connection
    TODO: Run migrations on test database
    TODO: Yield session
    TODO: Rollback and cleanup after test
    """
    pytest.skip("Test stub - implement during task 3.2")
    yield None


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


class TestParseExportDatabaseIntegration:
    """Tests for database integration."""

    @pytest.mark.asyncio
    async def test_parse_export_creates_media_events_in_db(
        self, parse_export_input: dict, db_session
    ):
        """Test that parse_export creates media_event rows in database."""
        # Arrange
        # TODO: Create test ZIP with videos
        # TODO: Mock Supabase Storage to return test ZIP
        # TODO: Verify media_events table is initially empty

        # Act
        # TODO: result = handler(parse_export_input, mock_context)

        # Assert
        # TODO: Query media_events table
        # TODO: Verify correct number of rows were created
        # TODO: Verify each row has correct user_id
        # TODO: Verify each row has correct upload_id
        # TODO: Verify each row has processing_state == "pending"
        # TODO: Verify each row has deterministic ID (uuid5)
        pytest.skip("Test stub - implement during task 3.2")

    @pytest.mark.asyncio
    async def test_parse_export_creates_pipeline_run(self, parse_export_input: dict, db_session):
        """Test that parse_export creates upload_pipeline_runs record."""
        # Arrange
        # TODO: Create test ZIP with videos
        # TODO: Mock Supabase Storage to return test ZIP
        # TODO: Verify upload_pipeline_runs table is initially empty

        # Act
        # TODO: result = handler(parse_export_input, mock_context)

        # Assert
        # TODO: Query upload_pipeline_runs table
        # TODO: Verify one row was created
        # TODO: Verify row has correct upload_id
        # TODO: Verify row has correct user_id
        # TODO: Verify row has status == "processing"
        # TODO: Verify row has total_videos matching result.total_items
        # TODO: Verify row has started_at timestamp
        pytest.skip("Test stub - implement during task 3.2")

    @pytest.mark.asyncio
    async def test_parse_export_upserts_existing_media_events(
        self, parse_export_input: dict, db_session
    ):
        """Test that parse_export upserts existing media_event rows on retry."""
        # Arrange
        # TODO: Create test ZIP with videos
        # TODO: Mock Supabase Storage to return test ZIP
        # TODO: Call handler once to create initial media_events
        # TODO: Modify one media_event in database

        # Act
        # TODO: Call handler again with same input (retry scenario)

        # Assert
        # TODO: Query media_events table
        # TODO: Verify row count is same (no duplicates)
        # TODO: Verify updated_at timestamp changed on modified row
        # TODO: Verify upload_id and interaction_type were updated per upsert logic
        pytest.skip("Test stub - implement during task 3.2")

    @pytest.mark.asyncio
    async def test_parse_export_respects_rls_policies(self, parse_export_input: dict, db_session):
        """Test that created media_events respect RLS policies."""
        # Arrange
        # TODO: Create test ZIP with videos
        # TODO: Mock Supabase Storage to return test ZIP

        # Act
        # TODO: result = handler(parse_export_input, mock_context)

        # Assert
        # TODO: Verify media_events are created with correct user_id
        # TODO: Attempt to query media_events with different user_id (should fail RLS)
        # TODO: Verify RLS prevents cross-user access
        pytest.skip("Test stub - implement during task 3.2")


class TestParseExportStorageIntegration:
    """Tests for Supabase Storage integration."""

    @pytest.mark.asyncio
    async def test_parse_export_deletes_zip_on_success(self, parse_export_input: dict):
        """Test that parse_export deletes ZIP from storage after successful parsing."""
        # Arrange
        # TODO: Create test ZIP
        # TODO: Mock Supabase Storage upload to place ZIP in bucket
        # TODO: Verify ZIP exists before parsing

        # Act
        # TODO: result = handler(parse_export_input, mock_context)

        # Assert
        # TODO: Verify ZIP was deleted from storage
        # TODO: Verify delete was called with correct storage_path
        pytest.skip("Test stub - implement during task 3.2")

    @pytest.mark.asyncio
    async def test_parse_export_deletes_zip_on_failure(self, parse_export_input: dict):
        """Test that parse_export deletes ZIP even when parsing fails."""
        # Arrange
        # TODO: Create invalid/corrupted ZIP
        # TODO: Mock Supabase Storage to return invalid ZIP
        # TODO: Verify ZIP exists before parsing

        # Act & Assert
        # TODO: Call handler and expect exception
        # TODO: Verify ZIP was still deleted (compensating cleanup)
        # TODO: Verify delete was called even after exception
        pytest.skip("Test stub - implement during task 3.2")

    @pytest.mark.asyncio
    async def test_parse_export_downloads_zip_from_storage(self, parse_export_input: dict):
        """Test that parse_export downloads ZIP from correct storage path."""
        # Arrange
        # TODO: Create test ZIP
        # TODO: Mock Supabase Storage with test ZIP
        # TODO: Track download calls

        # Act
        # TODO: result = handler(parse_export_input, mock_context)

        # Assert
        # TODO: Verify storage download was called
        # TODO: Verify correct storage_path was used
        # TODO: Verify correct bucket was accessed
        pytest.skip("Test stub - implement during task 3.2")


class TestParseExportEndToEnd:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    async def test_parse_export_full_pipeline_liked_scope(
        self, parse_export_input: dict, db_session
    ):
        """Test full pipeline with liked scope from ZIP to database."""
        # Arrange
        # TODO: Create realistic test ZIP with liked videos
        # TODO: Mock Supabase Storage to return test ZIP
        # TODO: Set scope to "liked"

        # Act
        # TODO: result = handler(parse_export_input, mock_context)

        # Assert
        # TODO: Verify output format matches ParseExportOutput schema
        # TODO: Verify media_events created in database
        # TODO: Verify upload_pipeline_runs created in database
        # TODO: Verify ZIP deleted from storage
        # TODO: Verify all media_items have interaction_type == "liked"
        # TODO: Verify favorited_count == 0
        pytest.skip("Test stub - implement during task 3.2")

    @pytest.mark.asyncio
    async def test_parse_export_full_pipeline_both_scope(
        self, parse_export_input: dict, db_session
    ):
        """Test full pipeline with both scope from ZIP to database."""
        # Arrange
        # TODO: Create realistic test ZIP with both liked and favorited videos
        # TODO: Mock Supabase Storage to return test ZIP
        # TODO: Set scope to "both"

        # Act
        # TODO: result = handler(parse_export_input, mock_context)

        # Assert
        # TODO: Verify output format matches ParseExportOutput schema
        # TODO: Verify all media_events created (liked + favorited)
        # TODO: Verify upload_pipeline_runs has correct total_videos
        # TODO: Verify ZIP deleted from storage
        # TODO: Verify liked_count + favorited_count == total_items
        pytest.skip("Test stub - implement during task 3.2")

    @pytest.mark.asyncio
    async def test_parse_export_handles_large_export(self, parse_export_input: dict, db_session):
        """Test parse_export handles large export (1000+ videos) efficiently."""
        # Arrange
        # TODO: Create test ZIP with 1000+ video URLs
        # TODO: Mock Supabase Storage to return large ZIP
        # TODO: Track execution time

        # Act
        # TODO: result = handler(parse_export_input, mock_context)

        # Assert
        # TODO: Verify all 1000+ media_events created
        # TODO: Verify execution completes within reasonable time
        # TODO: Verify memory usage is acceptable
        # TODO: Verify database operations are batched/efficient
        pytest.skip("Test stub - implement during task 3.2")


class TestParseExportErrorRecovery:
    """Tests for error recovery and retry behavior."""

    @pytest.mark.asyncio
    async def test_parse_export_retries_on_database_error(
        self, parse_export_input: dict, db_session
    ):
        """Test that parse_export is safe to retry on database errors."""
        # Arrange
        # TODO: Create test ZIP
        # TODO: Mock database to fail on first attempt
        # TODO: Mock database to succeed on second attempt

        # Act
        # TODO: First call fails with database error
        # TODO: Second call succeeds

        # Assert
        # TODO: Verify second call creates media_events successfully
        # TODO: Verify no duplicate media_events (idempotent)
        # TODO: Verify deterministic IDs prevent conflicts
        pytest.skip("Test stub - implement during task 3.2")

    @pytest.mark.asyncio
    async def test_parse_export_retries_on_storage_error(
        self, parse_export_input: dict, db_session
    ):
        """Test that parse_export is safe to retry on storage errors."""
        # Arrange
        # TODO: Create test ZIP
        # TODO: Mock storage to fail on first download attempt
        # TODO: Mock storage to succeed on second attempt

        # Act
        # TODO: First call fails with storage error
        # TODO: Second call succeeds

        # Assert
        # TODO: Verify second call completes successfully
        # TODO: Verify no partial state from first attempt
        pytest.skip("Test stub - implement during task 3.2")
