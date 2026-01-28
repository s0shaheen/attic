"""Text Fusion Lambda - combines caption, hashtags, transcript, OCR, and visual tags."""

import json

from common.logger import get_logger

logger = get_logger("text_fusion")


def handler(event: dict, context: object) -> dict:
    """Fuse all text sources into a unified representation.

    Combines caption, hashtags, transcript, OCR text, and visual tags
    into a single text field for embedding generation.

    Args:
        event: Lambda event containing all text sources for a video.
        context: Lambda execution context.

    Returns:
        Response with fused text output.
    """
    logger.info(
        "Starting text_fusion",
        extra={"upload_id": event.get("upload_id"), "function": "text_fusion"},
    )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {"status": "stub", "function": "text_fusion", "event": event}
        ),
    }
