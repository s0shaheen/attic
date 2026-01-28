"""Media Download Lambda - downloads video/images to S3 temp bucket."""

import json

from common.logger import get_logger

logger = get_logger("media_download")


def handler(event: dict, context: object) -> dict:
    """Download video or image media to S3 temporary storage.

    Args:
        event: Lambda event containing media URL and video metadata.
        context: Lambda execution context.

    Returns:
        Response with S3 path of downloaded media.
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
