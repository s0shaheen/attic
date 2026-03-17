"""Tests for the unified pipeline handler Lambda function.

Tests the handler entry point, _ensure_pipeline_run, and end-to-end
pipeline orchestration with mocked external dependencies.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

# Ensure the lambdas directory is on sys.path so we can import the handler
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lambdas"))

from app.services.pipeline import (  # noqa: E402, I001
    _ensure_pipeline_run,
    _extract_platform_id,
    _fuse_text,
    _normalize_tiktok_url,
)
from pipeline.handler import handler  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sqs_event(body: dict) -> dict:
    """Build an SQS event wrapping a single message body."""
    return {"Records": [{"body": json.dumps(body)}]}


def _make_context(request_id: str = "test-request-123") -> MagicMock:
    """Build a mock Lambda context object."""
    ctx = MagicMock()
    ctx.aws_request_id = request_id
    return ctx


def _make_message_body(
    upload_id: str | None = None,
    user_id: str | None = None,
    scope: str = "both",
) -> dict:
    """Build a standard pipeline message body."""
    return {
        "upload_id": upload_id or str(uuid4()),
        "user_id": user_id or str(uuid4()),
        "storage_path": "uploads/test-user/test-upload/export.zip",
        "scope": scope,
    }


def _make_mock_session():
    """Create a mock SQLAlchemy Session with commonly needed methods."""
    session = MagicMock()
    session.execute.return_value = MagicMock()
    session.flush.return_value = None
    session.commit.return_value = None
    session.close.return_value = None
    return session


def _make_pipeline_run_mock(run_id: str | None = None, status: str = "processing"):
    """Create a mock UploadPipelineRun object."""
    run = MagicMock()
    run.id = UUID(run_id) if run_id else uuid4()
    run.status = status
    return run


def _make_video_reference(url: str, interaction_type: str = "liked"):
    """Create a mock TikTokVideoReference-like object."""
    ref = MagicMock()
    ref.url = url
    ref.interaction_type = interaction_type
    ref.timestamp = datetime(2025, 6, 15, 12, 0, 0)
    return ref


def _make_parsed_export(liked_urls: list[str], favorited_urls: list[str] | None = None):
    """Create a mock TikTokParsedExport-like object."""
    parsed = MagicMock()
    parsed.liked_videos = [_make_video_reference(u, "liked") for u in liked_urls]
    parsed.favorited_videos = [
        _make_video_reference(u, "favorited") for u in (favorited_urls or [])
    ]
    return parsed


# ---------------------------------------------------------------------------
# TestHandler — handler entry point
# ---------------------------------------------------------------------------


class TestHandler:
    """Tests for the Lambda handler entry point."""

    def test_empty_records_returns_200_no_records(self):
        """Handler with no SQS records returns 200 with 'No records' message."""
        result = handler({"Records": []}, _make_context())
        assert result["statusCode"] == 200
        assert result["body"] == "No records"

    def test_missing_records_key_returns_200_no_records(self):
        """Handler with missing Records key returns 200 with 'No records' message."""
        result = handler({}, _make_context())
        assert result["statusCode"] == 200
        assert result["body"] == "No records"

    def test_handler_parses_sqs_body_and_calls_steps(self):
        """Handler correctly parses the SQS body and calls all 4 steps."""
        upload_id = str(uuid4())
        user_id = str(uuid4())
        body = _make_message_body(upload_id=upload_id, user_id=user_id)
        event = _make_sqs_event(body)

        mock_session = _make_mock_session()
        mock_event_ids = [str(uuid4()), str(uuid4())]

        with (
            patch("app.services.pipeline._session", return_value=mock_session),
            patch("app.services.pipeline._ensure_pipeline_run", return_value=str(uuid4())),
            patch(
                "app.services.pipeline.step_parse_export", return_value=mock_event_ids
            ) as mock_parse,
            patch("app.services.pipeline.step_apify_enrich") as mock_apify,
            patch("app.services.pipeline.step_subtitle_fetch") as mock_subtitle,
            patch("app.services.pipeline.step_embed") as mock_embed,
        ):
            result = handler(event, _make_context())

        assert result["statusCode"] == 200
        response_body = json.loads(result["body"])
        assert response_body["upload_id"] == upload_id
        assert response_body["items_processed"] == 2
        assert response_body["status"] == "complete"

        mock_parse.assert_called_once()
        mock_apify.assert_called_once()
        mock_subtitle.assert_called_once()
        mock_embed.assert_called_once()

    def test_handler_default_scope_is_both(self):
        """Handler defaults scope to 'both' when not specified in body."""
        body = _make_message_body()
        del body["scope"]
        event = _make_sqs_event(body)

        mock_session = _make_mock_session()

        with (
            patch("app.services.pipeline._session", return_value=mock_session),
            patch("app.services.pipeline._ensure_pipeline_run", return_value=str(uuid4())),
            patch("app.services.pipeline.step_parse_export", return_value=[]) as mock_parse,
            patch("app.services.pipeline.step_apify_enrich"),
            patch("app.services.pipeline.step_subtitle_fetch"),
            patch("app.services.pipeline.step_embed"),
        ):
            handler(event, _make_context())

        # Verify scope defaults to "both"
        call_args = mock_parse.call_args
        assert call_args[0][4] == "both"  # 5th positional arg is scope

    def test_handler_propagates_exception_after_marking_failed(self):
        """Handler marks upload as failed and re-raises on exception."""
        body = _make_message_body()
        event = _make_sqs_event(body)

        mock_session = _make_mock_session()

        with (
            patch("app.services.pipeline._session", return_value=mock_session),
            patch("app.services.pipeline._ensure_pipeline_run", return_value=str(uuid4())),
            patch(
                "app.services.pipeline.step_parse_export",
                side_effect=RuntimeError("download failed"),
            ),
            patch("app.services.pipeline._mark_upload_failed") as mock_mark_failed,
        ):
            with pytest.raises(RuntimeError, match="download failed"):
                handler(event, _make_context())

        mock_mark_failed.assert_called_once_with(body["upload_id"])

    def test_handler_closes_session_on_success(self):
        """Handler closes the DB session on successful completion."""
        body = _make_message_body()
        event = _make_sqs_event(body)
        mock_session = _make_mock_session()

        with (
            patch("app.services.pipeline._session", return_value=mock_session),
            patch("app.services.pipeline._ensure_pipeline_run", return_value=str(uuid4())),
            patch("app.services.pipeline.step_parse_export", return_value=[]),
            patch("app.services.pipeline.step_apify_enrich"),
            patch("app.services.pipeline.step_subtitle_fetch"),
            patch("app.services.pipeline.step_embed"),
        ):
            handler(event, _make_context())

        mock_session.close.assert_called_once()

    def test_handler_closes_session_on_failure(self):
        """Handler closes the DB session even when an exception occurs."""
        body = _make_message_body()
        event = _make_sqs_event(body)
        mock_session = _make_mock_session()

        with (
            patch("app.services.pipeline._session", return_value=mock_session),
            patch("app.services.pipeline._ensure_pipeline_run", return_value=str(uuid4())),
            patch(
                "app.services.pipeline.step_parse_export",
                side_effect=RuntimeError("boom"),
            ),
            patch("app.services.pipeline._mark_upload_failed"),
        ):
            with pytest.raises(RuntimeError):
                handler(event, _make_context())

        mock_session.close.assert_called_once()


# ---------------------------------------------------------------------------
# TestEnsurePipelineRun
# ---------------------------------------------------------------------------


class TestEnsurePipelineRun:
    """Tests for _ensure_pipeline_run pipeline run creation/reuse."""

    def test_creates_new_run_when_none_exists(self):
        """Creates a new pipeline run when no active run exists for the upload."""
        session = _make_mock_session()
        session.execute.return_value.scalar_one_or_none.return_value = None

        # Track objects added to the session
        added_objects = []
        session.add.side_effect = lambda obj: added_objects.append(obj)

        # flush needs to set an id on the added object
        def flush_side_effect():
            for obj in added_objects:
                if not hasattr(obj, "id") or obj.id is None:
                    obj.id = uuid4()

        session.flush.side_effect = flush_side_effect

        upload_id = str(uuid4())
        user_id = str(uuid4())

        result = _ensure_pipeline_run(session, upload_id, user_id)

        assert result is not None
        assert isinstance(result, str)
        # Verify a UUID was returned (valid UUID string)
        UUID(result)
        session.add.assert_called_once()
        session.flush.assert_called_once()

    def test_reuses_existing_active_run(self):
        """Returns existing run ID when an active (pending/processing) run exists."""
        session = _make_mock_session()
        existing_run_id = uuid4()
        existing_run = _make_pipeline_run_mock(str(existing_run_id))
        session.execute.return_value.scalar_one_or_none.return_value = existing_run

        upload_id = str(uuid4())
        user_id = str(uuid4())

        result = _ensure_pipeline_run(session, upload_id, user_id)

        assert result == str(existing_run_id)
        # Should NOT add a new object
        session.add.assert_not_called()

    def test_new_run_has_processing_status(self):
        """Newly created pipeline run has status 'processing'."""
        session = _make_mock_session()
        session.execute.return_value.scalar_one_or_none.return_value = None

        added_objects = []
        session.add.side_effect = lambda obj: added_objects.append(obj)

        def flush_side_effect():
            for obj in added_objects:
                if not hasattr(obj, "id") or obj.id is None:
                    obj.id = uuid4()

        session.flush.side_effect = flush_side_effect

        _ensure_pipeline_run(session, str(uuid4()), str(uuid4()))

        assert len(added_objects) == 1
        run = added_objects[0]
        assert run.status == "processing"
        assert run.started_at is not None


# ---------------------------------------------------------------------------
# TestPipelineEndToEnd
# ---------------------------------------------------------------------------


class TestPipelineEndToEnd:
    """End-to-end tests for the full pipeline flow."""

    def test_full_pipeline_success_marks_upload_complete(self):
        """Full pipeline: all 4 steps run, upload and pipeline run marked complete."""
        upload_id = str(uuid4())
        user_id = str(uuid4())
        pipeline_run_id = str(uuid4())
        body = _make_message_body(upload_id=upload_id, user_id=user_id)
        event = _make_sqs_event(body)

        mock_session = _make_mock_session()
        media_event_ids = [str(uuid4()) for _ in range(3)]

        with (
            patch("app.services.pipeline._session", return_value=mock_session),
            patch(
                "app.services.pipeline._ensure_pipeline_run",
                return_value=pipeline_run_id,
            ),
            patch(
                "app.services.pipeline.step_parse_export",
                return_value=media_event_ids,
            ),
            patch("app.services.pipeline.step_apify_enrich"),
            patch("app.services.pipeline.step_subtitle_fetch"),
            patch("app.services.pipeline.step_embed"),
        ):
            result = handler(event, _make_context())

        response_body = json.loads(result["body"])
        assert response_body["status"] == "complete"
        assert response_body["items_processed"] == 3

        # Verify session.execute was called multiple times (for updates)
        assert mock_session.execute.call_count > 0
        # Verify session was committed
        assert mock_session.commit.call_count > 0

    def test_step_order_is_correct(self):
        """Pipeline steps execute in order: parse -> apify -> subtitle -> embed."""
        body = _make_message_body()
        event = _make_sqs_event(body)

        mock_session = _make_mock_session()
        call_order = []

        def track_parse(*args, **kwargs):
            call_order.append("parse")
            return [str(uuid4())]

        def track_apify(*args, **kwargs):
            call_order.append("apify")

        def track_subtitle(*args, **kwargs):
            call_order.append("subtitle")

        def track_embed(*args, **kwargs):
            call_order.append("embed")

        with (
            patch("app.services.pipeline._session", return_value=mock_session),
            patch("app.services.pipeline._ensure_pipeline_run", return_value=str(uuid4())),
            patch("app.services.pipeline.step_parse_export", side_effect=track_parse),
            patch("app.services.pipeline.step_apify_enrich", side_effect=track_apify),
            patch("app.services.pipeline.step_subtitle_fetch", side_effect=track_subtitle),
            patch("app.services.pipeline.step_embed", side_effect=track_embed),
        ):
            handler(event, _make_context())

        assert call_order == ["parse", "apify", "subtitle", "embed"]

    def test_pipeline_failure_at_step2_marks_upload_failed(self):
        """If step 2 (apify) fails, upload is marked as failed."""
        body = _make_message_body()
        event = _make_sqs_event(body)

        mock_session = _make_mock_session()

        with (
            patch("app.services.pipeline._session", return_value=mock_session),
            patch("app.services.pipeline._ensure_pipeline_run", return_value=str(uuid4())),
            patch("app.services.pipeline.step_parse_export", return_value=[str(uuid4())]),
            patch(
                "app.services.pipeline.step_apify_enrich",
                side_effect=RuntimeError("Apify timeout"),
            ),
            patch("app.services.pipeline._mark_upload_failed") as mock_mark_failed,
        ):
            with pytest.raises(RuntimeError, match="Apify timeout"):
                handler(event, _make_context())

        mock_mark_failed.assert_called_once_with(body["upload_id"])

    def test_pipeline_with_zero_items_still_completes(self):
        """Pipeline completes successfully even when parse returns zero items."""
        body = _make_message_body()
        event = _make_sqs_event(body)

        mock_session = _make_mock_session()

        with (
            patch("app.services.pipeline._session", return_value=mock_session),
            patch("app.services.pipeline._ensure_pipeline_run", return_value=str(uuid4())),
            patch("app.services.pipeline.step_parse_export", return_value=[]),
            patch("app.services.pipeline.step_apify_enrich") as mock_apify,
            patch("app.services.pipeline.step_subtitle_fetch") as mock_subtitle,
            patch("app.services.pipeline.step_embed") as mock_embed,
        ):
            result = handler(event, _make_context())

        response_body = json.loads(result["body"])
        assert response_body["status"] == "complete"
        assert response_body["items_processed"] == 0

        # Steps 2-4 are still called even with empty list
        mock_apify.assert_called_once()
        mock_subtitle.assert_called_once()
        mock_embed.assert_called_once()


# ---------------------------------------------------------------------------
# TestURLHelpers
# ---------------------------------------------------------------------------


class TestURLHelpers:
    """Tests for URL normalization and platform ID extraction."""

    def test_normalize_tiktok_url_replaces_tiktokv(self):
        """_normalize_tiktok_url replaces tiktokv.com with tiktok.com."""
        url = "https://www.tiktokv.com/share/video/7123456789/"
        result = _normalize_tiktok_url(url)
        assert "tiktokv.com" not in result
        assert "tiktok.com" in result

    def test_normalize_tiktok_url_preserves_valid_url(self):
        """_normalize_tiktok_url preserves already-valid tiktok.com URLs."""
        url = "https://www.tiktok.com/@user/video/7123456789"
        result = _normalize_tiktok_url(url)
        assert result == url

    def test_extract_platform_id_from_video_url(self):
        """_extract_platform_id extracts video ID from standard TikTok URL."""
        url = "https://www.tiktok.com/@user/video/7123456789"
        result = _extract_platform_id(url)
        assert result == "7123456789"

    def test_extract_platform_id_returns_none_for_short_url(self):
        """_extract_platform_id returns None for short URLs without /video/ path."""
        url = "https://vm.tiktok.com/ZM2abc/"
        result = _extract_platform_id(url)
        assert result is None


# ---------------------------------------------------------------------------
# TestFuseText
# ---------------------------------------------------------------------------


class TestFuseText:
    """Tests for _fuse_text text fusion helper."""

    def test_fuse_text_with_all_fields(self):
        """_fuse_text combines all available text fields."""
        event = MagicMock()
        event.caption_text = "Funny cat video"
        event.hashtags = ["cats", "funny"]
        event.subtitle_text = "meow meow"
        event.creator_username = "catperson"
        event.music_name = "Original Sound"

        result = _fuse_text(event)
        assert "Funny cat video" in result
        assert "#cats" in result
        assert "#funny" in result
        assert "meow meow" in result
        assert "@catperson" in result
        assert "Original Sound" in result

    def test_fuse_text_with_no_fields(self):
        """_fuse_text returns 'untitled tiktok' when no text fields exist."""
        event = MagicMock()
        event.caption_text = None
        event.hashtags = None
        event.subtitle_text = None
        event.creator_username = None
        event.music_name = None

        result = _fuse_text(event)
        assert result == "untitled tiktok"

    def test_fuse_text_with_partial_fields(self):
        """_fuse_text handles partial field availability."""
        event = MagicMock()
        event.caption_text = "Hello world"
        event.hashtags = None
        event.subtitle_text = None
        event.creator_username = "testuser"
        event.music_name = None

        result = _fuse_text(event)
        assert "Hello world" in result
        assert "@testuser" in result
        assert "|" in result
