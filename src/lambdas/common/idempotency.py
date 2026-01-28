"""Idempotency key generation helper for Lambda functions."""

import hashlib
import uuid


def generate_idempotency_key(upload_id: str, video_url: str) -> str:
    """Generate a deterministic idempotency key for a video processing operation.

    Uses SHA-256 hash of upload_id and video_url to create a stable,
    deterministic key that is safe to use across retries.

    Args:
        upload_id: The upload identifier (UUID string).
        video_url: The video URL being processed.

    Returns:
        A deterministic UUID string derived from the input parameters.
    """
    composite = f"{upload_id}:{video_url}"
    hash_bytes = hashlib.sha256(composite.encode("utf-8")).digest()
    # Use first 16 bytes to create a valid UUID v4-like identifier
    return str(uuid.UUID(bytes=hash_bytes[:16]))


def generate_idempotency_key_with_step(
    upload_id: str, video_url: str, step_name: str
) -> str:
    """Generate a deterministic idempotency key scoped to a processing step.

    Extends the base idempotency key with a step name to allow
    independent idempotency tracking per pipeline stage.

    Args:
        upload_id: The upload identifier (UUID string).
        video_url: The video URL being processed.
        step_name: The pipeline step name (e.g., "apify_enrich", "vision_analysis").

    Returns:
        A deterministic UUID string scoped to the specific processing step.
    """
    composite = f"{upload_id}:{video_url}:{step_name}"
    hash_bytes = hashlib.sha256(composite.encode("utf-8")).digest()
    return str(uuid.UUID(bytes=hash_bytes[:16]))
