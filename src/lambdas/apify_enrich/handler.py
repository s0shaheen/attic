"""Apify Enrich Lambda - fetches TikTok metadata via Apify (batched, 50 URLs/call)."""

import json

from common.logger import get_logger

logger = get_logger("apify_enrich")


def handler(event: dict, context: object) -> dict:
    """Fetch TikTok metadata for a batch of media URLs.

    Detects media_type from Apify response (is_slideshow, video_duration)
    and sets image_count/image_urls for slideshows.

    Args:
        event: Lambda event containing batch of URLs.
        context: Lambda execution context.

    Returns:
        Response with enriched metadata for each URL including media_type.
    """
    logger.info(
        "Starting apify_enrich",
        extra={"upload_id": event.get("upload_id"), "function": "apify_enrich"},
    )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {"status": "stub", "function": "apify_enrich", "event": event}
        ),
    }
