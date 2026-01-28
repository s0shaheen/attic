"""Apify Enrich Lambda - fetches TikTok metadata via Apify (batched, 50 URLs/call)."""

import json

from common.logger import get_logger

logger = get_logger("apify_enrich")


def handler(event: dict, context: object) -> dict:
    """Fetch TikTok metadata for a batch of video URLs.

    Args:
        event: Lambda event containing batch of URLs.
        context: Lambda execution context.

    Returns:
        Response with enriched metadata for each URL.
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
