"""Lambda entry point -- thin wrapper around app.services.pipeline.

Parses SQS event and delegates to run_pipeline().
All pipeline logic lives in app/services/pipeline.py.
"""

from __future__ import annotations

import json
from typing import Any

from app.services.pipeline import run_pipeline


def handler(event: dict, context: Any) -> dict:
    """Lambda handler: parse SQS message and run pipeline."""
    records = event.get("Records", [])
    if not records:
        return {"statusCode": 200, "body": "No records"}

    record = records[0]
    body = json.loads(record["body"])

    request_id = getattr(context, "aws_request_id", "local") if context else "local"

    return run_pipeline(
        upload_id=body["upload_id"],
        user_id=body["user_id"],
        storage_path=body["storage_path"],
        scope=body.get("scope", "both"),
        request_id=request_id,
    )
