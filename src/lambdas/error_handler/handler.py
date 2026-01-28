"""Error Handler Lambda - handles pipeline failures and notifies users."""

import json

from common.logger import get_logger

logger = get_logger("error_handler")


def handler(event: dict, context: object) -> dict:
    """Handle pipeline errors and log failure details.

    Processes error information from Step Functions Catch blocks,
    logs structured error data, and marks affected videos as failed.

    Args:
        event: Lambda event containing error details from state machine.
        context: Lambda execution context.

    Returns:
        Response with error handling status.
    """
    logger.error(
        "Pipeline error handled",
        extra={
            "upload_id": event.get("upload_id"),
            "function": "error_handler",
            "error": event.get("error", {}),
        },
    )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {"status": "stub", "function": "error_handler", "event": event}
        ),
    }
