"""Unit tests for Lambda function stub handlers."""

import json
import sys
from pathlib import Path

import pytest

# Add the lambdas directory to the Python path so common module is importable
LAMBDAS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LAMBDAS_DIR))

from common.idempotency import (
    generate_idempotency_key,
    generate_idempotency_key_with_step,
)
from common.logger import get_logger


# ---------- Logger Tests ----------


def test_get_logger_returns_logger():
    """Logger utility returns a configured Logger instance."""
    logger = get_logger("test_function")
    assert logger is not None
    assert logger.name == "test_function"


def test_get_logger_caches_logger():
    """Logger utility returns same instance for same function name."""
    logger1 = get_logger("cached_test")
    logger2 = get_logger("cached_test")
    assert logger1 is logger2


def test_get_logger_with_correlation_id():
    """Logger utility accepts optional correlation ID."""
    logger = get_logger("corr_test", correlation_id="test-corr-123")
    assert logger.correlation_id == "test-corr-123"  # type: ignore[attr-defined]


def test_get_logger_generates_correlation_id():
    """Logger utility auto-generates correlation ID when not provided."""
    logger = get_logger("auto_corr_test_" + str(id(object())))
    assert hasattr(logger, "correlation_id")
    assert logger.correlation_id  # type: ignore[attr-defined]


# ---------- Idempotency Tests ----------


def test_generate_idempotency_key_deterministic():
    """Idempotency key is deterministic for same inputs."""
    key1 = generate_idempotency_key("upload-123", "https://tiktok.com/video/1")
    key2 = generate_idempotency_key("upload-123", "https://tiktok.com/video/1")
    assert key1 == key2


def test_generate_idempotency_key_different_inputs():
    """Idempotency key differs for different upload IDs."""
    key1 = generate_idempotency_key("upload-123", "https://tiktok.com/video/1")
    key2 = generate_idempotency_key("upload-456", "https://tiktok.com/video/1")
    assert key1 != key2


def test_generate_idempotency_key_different_urls():
    """Idempotency key differs for different video URLs."""
    key1 = generate_idempotency_key("upload-123", "https://tiktok.com/video/1")
    key2 = generate_idempotency_key("upload-123", "https://tiktok.com/video/2")
    assert key1 != key2


def test_generate_idempotency_key_valid_uuid_format():
    """Idempotency key is a valid UUID string."""
    import uuid

    key = generate_idempotency_key("upload-123", "https://tiktok.com/video/1")
    # Should not raise ValueError
    uuid.UUID(key)


def test_generate_idempotency_key_with_step_deterministic():
    """Step-scoped idempotency key is deterministic."""
    key1 = generate_idempotency_key_with_step("upload-1", "url-1", "apify_enrich")
    key2 = generate_idempotency_key_with_step("upload-1", "url-1", "apify_enrich")
    assert key1 == key2


def test_generate_idempotency_key_with_step_differs_by_step():
    """Step-scoped keys differ when step names differ."""
    key1 = generate_idempotency_key_with_step("upload-1", "url-1", "apify_enrich")
    key2 = generate_idempotency_key_with_step("upload-1", "url-1", "vision_analysis")
    assert key1 != key2


# ---------- Stub Handler Tests ----------

# Import all stub handlers
parse_export = __import__("parse_export.handler", fromlist=["handler"])
apify_enrich = __import__("apify_enrich.handler", fromlist=["handler"])
media_download = __import__("media_download.handler", fromlist=["handler"])
subtitle_fetch = __import__("subtitle_fetch.handler", fromlist=["handler"])
whisper_transcribe = __import__("whisper_transcribe.handler", fromlist=["handler"])
vision_analysis = __import__("vision_analysis.handler", fromlist=["handler"])
text_fusion = __import__("text_fusion.handler", fromlist=["handler"])
embedding = __import__("embedding.handler", fromlist=["handler"])
derived_fields = __import__("derived_fields.handler", fromlist=["handler"])
search_index = __import__("search_index.handler", fromlist=["handler"])
error_handler = __import__("error_handler.handler", fromlist=["handler"])

STUB_HANDLERS = [
    ("parse_export", parse_export.handler),
    ("apify_enrich", apify_enrich.handler),
    ("media_download", media_download.handler),
    ("subtitle_fetch", subtitle_fetch.handler),
    ("whisper_transcribe", whisper_transcribe.handler),
    ("vision_analysis", vision_analysis.handler),
    ("text_fusion", text_fusion.handler),
    ("embedding", embedding.handler),
    ("derived_fields", derived_fields.handler),
    ("search_index", search_index.handler),
    ("error_handler", error_handler.handler),
]


class MockContext:
    """Mock AWS Lambda context object."""

    function_name = "test-function"
    memory_limit_in_mb = 512
    invoked_function_arn = "arn:aws:lambda:us-east-1:123456789:function:test"
    aws_request_id = "test-request-id"


@pytest.mark.parametrize("function_name,handler_fn", STUB_HANDLERS)
def test_stub_handler_returns_200(function_name, handler_fn):
    """Each stub handler returns statusCode 200."""
    event = {"upload_id": "test-upload", "test": True}
    result = handler_fn(event, MockContext())
    assert result["statusCode"] == 200


@pytest.mark.parametrize("function_name,handler_fn", STUB_HANDLERS)
def test_stub_handler_returns_stub_status(function_name, handler_fn):
    """Each stub handler returns status: stub in body."""
    event = {"upload_id": "test-upload"}
    result = handler_fn(event, MockContext())
    body = json.loads(result["body"])
    assert body["status"] == "stub"


@pytest.mark.parametrize("function_name,handler_fn", STUB_HANDLERS)
def test_stub_handler_returns_function_name(function_name, handler_fn):
    """Each stub handler returns its own function name in body."""
    event = {"upload_id": "test-upload"}
    result = handler_fn(event, MockContext())
    body = json.loads(result["body"])
    assert body["function"] == function_name


@pytest.mark.parametrize("function_name,handler_fn", STUB_HANDLERS)
def test_stub_handler_echoes_event(function_name, handler_fn):
    """Each stub handler echoes the input event in body."""
    event = {"upload_id": "test-upload", "custom_key": "custom_value"}
    result = handler_fn(event, MockContext())
    body = json.loads(result["body"])
    assert body["event"] == event


def test_stub_handler_with_empty_event():
    """Stub handlers handle empty event gracefully."""
    event = {}
    result = parse_export.handler(event, MockContext())
    body = json.loads(result["body"])
    assert body["status"] == "stub"
    assert body["event"] == {}


def test_error_handler_handles_error_event():
    """Error handler processes events with error information."""
    event = {
        "upload_id": "test-upload",
        "error": {
            "Error": "States.TaskFailed",
            "Cause": "Lambda function failed",
        },
    }
    result = error_handler.handler(event, MockContext())
    body = json.loads(result["body"])
    assert body["status"] == "stub"
    assert body["function"] == "error_handler"
