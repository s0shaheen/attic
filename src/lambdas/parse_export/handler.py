"""Parse Export Lambda - extracts media URLs from TikTok data export ZIP."""

import json
import logging

from common.logger import get_logger

logger = get_logger("parse_export")


def handler(event: dict, context: object) -> dict:
    """Parse TikTok export ZIP and extract media URLs.

    Extracts URLs for videos, images, and slideshows from the export,
    creating media_event rows with appropriate media_type classification.

    Args:
        event: Lambda event containing upload metadata.
        context: Lambda execution context.

    Returns:
        Response with status and extracted media URLs as $.media_items.
    """
    logger.info(
        "Starting parse_export",
        extra={"upload_id": event.get("upload_id"), "function": "parse_export"},
    )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {"status": "stub", "function": "parse_export", "event": event}
        ),
    }
