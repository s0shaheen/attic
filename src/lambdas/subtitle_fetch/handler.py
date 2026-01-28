"""Subtitle Fetch Lambda - retrieves subtitles for a video if available."""

import json

from common.logger import get_logger

logger = get_logger("subtitle_fetch")


def handler(event: dict, context: object) -> dict:
    """Fetch subtitles for a video from the source platform.

    Args:
        event: Lambda event containing video URL and metadata.
        context: Lambda execution context.

    Returns:
        Response with subtitle text and has_subtitles flag.
    """
    logger.info(
        "Starting subtitle_fetch",
        extra={"upload_id": event.get("upload_id"), "function": "subtitle_fetch"},
    )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {"status": "stub", "function": "subtitle_fetch", "event": event}
        ),
    }
