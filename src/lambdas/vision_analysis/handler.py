"""Vision Analysis Lambda - GPT-4 Vision tagging (batched, 5 images/call)."""

import json

from common.logger import get_logger

logger = get_logger("vision_analysis")


def handler(event: dict, context: object) -> dict:
    """Analyze media using GPT-4 Vision for visual tagging.

    Handles all media types:
    - VIDEO: Extracts and analyzes key frames
    - IMAGE: Analyzes the single image directly
    - SLIDESHOW: Analyzes all slideshow images

    Args:
        event: Lambda event containing S3 path to media.
        context: Lambda execution context.

    Returns:
        Response with visual tags and analysis results.
    """
    logger.info(
        "Starting vision_analysis",
        extra={"upload_id": event.get("upload_id"), "function": "vision_analysis"},
    )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {"status": "stub", "function": "vision_analysis", "event": event}
        ),
    }
