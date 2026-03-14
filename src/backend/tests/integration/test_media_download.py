"""
Integration tests for Media Download Lambda (Task 3.4).

Task: 3.4
Spec: docs/MVP/tasks/specs/3-3.4.md

These tests verify end-to-end behavior including:
- Real S3 uploads (LocalStack)
- Database updates (media_events, processing_steps)
- Step Functions integration
"""

from uuid import uuid4

import pytest


class TestMediaDownloadS3Integration:
    """Integration tests for S3 upload functionality."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_media_download_uploads_to_s3(self):
        """Test that Lambda uploads video to LocalStack S3."""
        # Arrange
        # TODO: Set up LocalStack S3 client
        # TODO: Create test bucket "attic-media-temp"
        # TODO: Mock HTTP client to return test video bytes
        # TODO: Create MediaDownloadInput
        uuid4()
        uuid4()

        # Act
        # TODO: Call lambda_handler

        # Assert
        # TODO: Verify object exists in S3 at correct path
        # TODO: Verify object size matches file_size_bytes
        # TODO: Verify object is retrievable
        pytest.skip("Test stub - implement during task 3.4")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_media_download_uploads_slideshow_images_to_s3(self):
        """Test that Lambda uploads multiple slideshow images to S3."""
        # Arrange
        # TODO: Set up LocalStack S3 client
        # TODO: Create test bucket
        # TODO: Mock HTTP client for 3 images
        # TODO: Create MediaDownloadInput with slideshow type

        # Act
        # TODO: Call lambda_handler

        # Assert
        # TODO: Verify 3 image objects exist in S3
        # TODO: Verify paths are image_0.jpg, image_1.jpg, image_2.jpg
        # TODO: Verify all objects are retrievable
        pytest.skip("Test stub - implement during task 3.4")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_media_download_s3_lifecycle_policy_exists(self):
        """Test that S3 bucket has 24h TTL lifecycle policy."""
        # Arrange
        # TODO: Set up LocalStack S3 client
        # TODO: Create test bucket with lifecycle configuration

        # Act
        # TODO: Get bucket lifecycle configuration

        # Assert
        # TODO: Verify lifecycle rule exists
        # TODO: Verify expiration set to 1 day (24 hours)
        # TODO: Verify rule applies to all objects in bucket
        pytest.skip("Test stub - implement during task 3.4")


class TestMediaDownloadDatabaseIntegration:
    """Integration tests for database updates."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_media_download_updates_media_events(self):
        """Test that Lambda updates media_events table with S3 paths."""
        # Arrange
        # TODO: Set up test database connection
        # TODO: Insert test media_event row
        # TODO: Mock HTTP and S3 clients
        # TODO: Create MediaDownloadInput with media_event_id

        # Act
        # TODO: Call lambda_handler

        # Assert
        # TODO: Query media_events table
        # TODO: Verify s3_video_path updated
        # TODO: Verify s3_thumbnail_path updated
        # TODO: Verify processing_substate == "media_downloaded"
        # TODO: Verify updated_at timestamp changed
        pytest.skip("Test stub - implement during task 3.4")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_media_download_updates_slideshow_media_events(self):
        """Test that Lambda updates media_events for slideshow type."""
        # Arrange
        # TODO: Set up test database
        # TODO: Insert test media_event with media_type="slideshow"
        # TODO: Mock HTTP and S3 clients
        # TODO: Create MediaDownloadInput with 3 images

        # Act
        # TODO: Call lambda_handler

        # Assert
        # TODO: Query media_events table
        # TODO: Verify s3_image_paths contains 3 paths (array column)
        # TODO: Verify image_count == 3
        # TODO: Verify processing_substate == "media_downloaded"
        pytest.skip("Test stub - implement during task 3.4")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_media_download_creates_processing_steps(self):
        """Test that Lambda creates processing_steps record."""
        # Arrange
        # TODO: Set up test database
        # TODO: Insert test media_event
        # TODO: Mock HTTP and S3 clients
        # TODO: Create MediaDownloadInput

        # Act
        # TODO: Call lambda_handler

        # Assert
        # TODO: Query processing_steps table
        # TODO: Verify row exists with step_type="MEDIA_DOWNLOAD"
        # TODO: Verify provider="aws_s3"
        # TODO: Verify status="completed"
        # TODO: Verify started_at and finished_at timestamps
        # TODO: Verify output_summary contains file_size_bytes
        pytest.skip("Test stub - implement during task 3.4")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_media_download_updates_processing_steps_on_retry(self):
        """Test that Lambda upserts processing_steps on retry (idempotency)."""
        # Arrange
        # TODO: Set up test database
        # TODO: Insert test media_event and initial processing_step
        # TODO: Mock HTTP and S3 clients
        # TODO: Create MediaDownloadInput

        # Act
        # TODO: Call lambda_handler (simulating retry)

        # Assert
        # TODO: Query processing_steps table
        # TODO: Verify only ONE row exists (upsert, not duplicate)
        # TODO: Verify finished_at updated to new timestamp
        pytest.skip("Test stub - implement during task 3.4")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_media_download_handles_failed_item_in_db(self):
        """Test that failed download creates processing_step with failed status."""
        # Arrange
        # TODO: Set up test database
        # TODO: Insert test media_event
        # TODO: Mock HTTP client to raise 404 error
        # TODO: Create MediaDownloadInput

        # Act
        # TODO: Call lambda_handler

        # Assert
        # TODO: Query processing_steps table
        # TODO: Verify status="failed"
        # TODO: Verify error_details contains error message
        # TODO: Verify media_events.processing_substate NOT updated
        pytest.skip("Test stub - implement during task 3.4")


class TestMediaDownloadStepFunctionsIntegration:
    """Integration tests for Step Functions invocation."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_media_download_invoked_by_step_functions(self):
        """Test that Lambda can be invoked as Map state from Step Functions."""
        # Arrange
        # TODO: Set up LocalStack Step Functions
        # TODO: Deploy minimal state machine with DownloadMedia Map state
        # TODO: Mock HTTP and S3 clients
        # TODO: Prepare state machine input with media_items array

        # Act
        # TODO: Start state machine execution
        # TODO: Wait for Map state to complete

        # Assert
        # TODO: Verify Lambda invoked for each media item
        # TODO: Verify Map state output contains downloaded_items
        # TODO: Verify execution succeeded
        pytest.skip("Test stub - implement during task 3.4")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_media_download_returns_output_for_next_state(self):
        """Test that Lambda output is correctly passed to next Step Functions state."""
        # Arrange
        # TODO: Set up LocalStack Step Functions
        # TODO: Deploy state machine with DownloadMedia -> NextState transition
        # TODO: Mock HTTP and S3 clients
        # TODO: Prepare state machine input

        # Act
        # TODO: Execute state machine through DownloadMedia state
        # TODO: Capture output passed to NextState

        # Assert
        # TODO: Verify NextState receives s3_video_path
        # TODO: Verify NextState receives media_event_id
        # TODO: Verify execution context preserved (upload_id, user_id)
        pytest.skip("Test stub - implement during task 3.4")


class TestMediaDownloadObservability:
    """Integration tests for logging and metrics."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_media_download_logs_structured_fields(self):
        """Test that Lambda emits structured logs with required fields."""
        # Arrange
        # TODO: Set up log capture
        # TODO: Mock HTTP and S3 clients
        # TODO: Create MediaDownloadInput
        uuid4()
        uuid4()

        # Act
        # TODO: Call lambda_handler

        # Assert
        # TODO: Verify logs contain upload_id
        # TODO: Verify logs contain user_id
        # TODO: Verify logs contain execution_arn
        # TODO: Verify logs contain step_name="MEDIA_DOWNLOAD"
        # TODO: Verify logs contain media_event_id
        # TODO: Verify logs contain media_type
        # TODO: Verify logs contain file_size_bytes
        # TODO: Verify logs contain duration_ms
        pytest.skip("Test stub - implement during task 3.4")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_media_download_emits_metrics(self):
        """Test that Lambda emits CloudWatch metrics."""
        # Arrange
        # TODO: Set up metric capture
        # TODO: Mock HTTP and S3 clients
        # TODO: Create MediaDownloadInput with multiple items

        # Act
        # TODO: Call lambda_handler

        # Assert
        # TODO: Verify metric "media_download.duration_ms" emitted
        # TODO: Verify metric "media_download.items_downloaded" emitted
        # TODO: Verify metric "media_download.items_failed" emitted
        # TODO: Verify metric "media_download.total_bytes" emitted
        pytest.skip("Test stub - implement during task 3.4")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_media_download_captures_errors_in_sentry(self):
        """Test that Lambda errors are captured in Sentry."""
        # Arrange
        # TODO: Set up Sentry mock/capture
        # TODO: Mock HTTP client to raise exception
        # TODO: Create MediaDownloadInput

        # Act
        # TODO: Call lambda_handler (expect error)

        # Assert
        # TODO: Verify Sentry event captured
        # TODO: Verify event has tag "upload_id"
        # TODO: Verify event has tag "media_type"
        # TODO: Verify breadcrumbs include "Downloading video"
        pytest.skip("Test stub - implement during task 3.4")
