"""Whisper Transcribe Lambda - transcribes audio via OpenAI Whisper when no subtitles."""

import json

from common.logger import get_logger

logger = get_logger("whisper_transcribe")


def handler(event: dict, context: object) -> dict:
    """Transcribe video audio using OpenAI Whisper API.

    Args:
        event: Lambda event containing S3 path to video.
        context: Lambda execution context.

    Returns:
        Response with transcription text.
    """
    logger.info(
        "Starting whisper_transcribe",
        extra={
            "upload_id": event.get("upload_id"),
            "function": "whisper_transcribe",
        },
    )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {"status": "stub", "function": "whisper_transcribe", "event": event}
        ),
    }
