"""Media Download Lambda - downloads video/images to S3 temp bucket."""

import json

from common.logger import get_logger

logger = get_logger("media_download")


def handler(event: dict, context: object) -> dict:
    """Download media to S3 temporary storage.

    Handles all media types based on media_type field:
    - VIDEO: Downloads video file
    - IMAGE: Downloads single image
    - SLIDESHOW: Downloads all images, stores paths in image_urls

    Args:
        event: Lambda event containing media URL and metadata.
        context: Lambda execution context.

    Returns:
        Response with S3 path(s) of downloaded media.
    """
    logger.info(
        "Starting media_download",
        extra={"upload_id": event.get("upload_id"), "function": "media_download"},
    )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {"status": "stub", "function": "media_download", "event": event}
        ),
    }
