"""Embedding Lambda - generates 1536-dim vectors via OpenAI (batched, 100/call)."""

import json

from common.logger import get_logger

logger = get_logger("embedding")


def handler(event: dict, context: object) -> dict:
    """Generate text embeddings using OpenAI embedding model.

    Args:
        event: Lambda event containing text to embed.
        context: Lambda execution context.

    Returns:
        Response with 1536-dimensional embedding vector.
    """
    logger.info(
        "Starting embedding",
        extra={"upload_id": event.get("upload_id"), "function": "embedding"},
    )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {"status": "stub", "function": "embedding", "event": event}
        ),
    }
