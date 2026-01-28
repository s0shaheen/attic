"""Search Index Lambda - updates full-text (GIN) and vector (ivfflat) indexes."""

import json

from common.logger import get_logger

logger = get_logger("search_index")


def handler(event: dict, context: object) -> dict:
    """Update search indexes with enriched video data.

    Updates both full-text search (GIN) and vector similarity (ivfflat)
    indexes in the database.

    Args:
        event: Lambda event containing enriched video data and embeddings.
        context: Lambda execution context.

    Returns:
        Response with index update status.
    """
    logger.info(
        "Starting search_index",
        extra={"upload_id": event.get("upload_id"), "function": "search_index"},
    )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {"status": "stub", "function": "search_index", "event": event}
        ),
    }
