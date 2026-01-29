---
name: lambda-patterns
description: Patterns for AWS Lambda functions in Attic's processing pipeline. Use when implementing pipeline steps, Step Functions integration, idempotency, or structured logging.
---

# Lambda Patterns for Attic Pipeline

## CRITICAL: Idempotency

Every Lambda MUST be idempotent. Step Functions retries failed invocations.

### Pattern 1: Deterministic IDs

Generate IDs from content, not randomly:

```python
from uuid import uuid5, NAMESPACE_URL

def get_media_event_id(user_id: str, platform_id: str) -> str:
    """
    Deterministic ID ensures idempotent upserts.
    Same user + platform_id always produces same UUID.
    """
    return str(uuid5(NAMESPACE_URL, f"{user_id}:{platform_id}"))
```

### Pattern 2: Upsert on Conflict

```python
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import func

async def save_media_event(db: AsyncSession, event: MediaEventCreate):
    """Upsert media event - safe for retries."""
    stmt = insert(MediaEvent).values(**event.dict())
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],  # or ["user_id", "platform", "platform_id"]
        set_={
            "caption_text": stmt.excluded.caption_text,
            "hashtags": stmt.excluded.hashtags,
            "updated_at": func.now()
        }
    )
    await db.execute(stmt)
    await db.commit()
```

### Pattern 3: Idempotency Key for Processing Steps

```python
async def record_processing_step(
    db: AsyncSession,
    media_event_id: str,
    step_type: str,
    attempt: int,
    status: str,
    **kwargs
):
    """
    Record step with unique constraint on (media_event_id, step_type, attempt).
    If already recorded, skip silently.
    """
    stmt = insert(ProcessingStep).values(
        id=str(uuid5(NAMESPACE_URL, f"{media_event_id}:{step_type}:{attempt}")),
        media_event_id=media_event_id,
        step_type=step_type,
        attempt=attempt,
        status=status,
        **kwargs
    ).on_conflict_do_nothing()
    await db.execute(stmt)
```

## Lambda Handler Structure

```python
# src/backend/lambdas/{step_name}/handler.py
import json
import logging
from typing import Any
import boto3

from app.core.config import settings
from app.db.session import get_db_session

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event: dict, context: Any) -> dict:
    """
    Lambda handler for {STEP_NAME} step.
    
    Input (from Step Functions):
    {
        "upload_id": "uuid",
        "user_id": "uuid",
        "execution_arn": "arn:aws:states:...",
        "batch_index": 0,        # for batched steps
        "items": [...]           # items to process
    }
    
    Output (to Step Functions):
    {
        "upload_id": "uuid",
        "batch_index": 0,
        "processed_count": 50,
        "failed_count": 2,
        "cost_usd": 0.104,
        "next_batch": {...}      # optional, for pagination
    }
    """
    # Extract inputs
    upload_id = event["upload_id"]
    user_id = event["user_id"]
    
    # Structured log: start
    logger.info(json.dumps({
        "event": "step_start",
        "step_name": "STEP_NAME",
        "upload_id": upload_id,
        "user_id": user_id,  # OK to log user_id, NOT email
        "item_count": len(event.get("items", []))
    }))
    
    try:
        with get_db_session() as db:
            # Process items
            processed = 0
            failed = 0
            total_cost = 0.0
            
            for item in event.get("items", []):
                try:
                    result = process_item(item)
                    await save_result(db, result)
                    processed += 1
                    total_cost += result.cost_usd
                except Exception as e:
                    failed += 1
                    logger.warning(json.dumps({
                        "event": "item_failed",
                        "upload_id": upload_id,
                        "item_id": item.get("id"),
                        "error": str(e)
                    }))
            
            db.commit()
        
        # Structured log: complete
        logger.info(json.dumps({
            "event": "step_complete",
            "step_name": "STEP_NAME",
            "upload_id": upload_id,
            "processed_count": processed,
            "failed_count": failed,
            "cost_usd": total_cost
        }))
        
        return {
            "upload_id": upload_id,
            "batch_index": event.get("batch_index", 0),
            "processed_count": processed,
            "failed_count": failed,
            "cost_usd": total_cost
        }
        
    except Exception as e:
        logger.error(json.dumps({
            "event": "step_error",
            "step_name": "STEP_NAME",
            "upload_id": upload_id,
            "error": str(e),
            "error_type": type(e).__name__
        }))
        raise  # Let Step Functions handle retry
```

## Step Functions State Machine (ASL)

```json
{
  "Comment": "Attic Media Processing Pipeline",
  "StartAt": "ParseExport",
  "States": {
    "ParseExport": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:attic-parse-export",
      "ResultPath": "$.parseResult",
      "Next": "CreateBatches",
      "Retry": [
        {
          "ErrorEquals": ["States.TaskFailed", "Lambda.ServiceException"],
          "IntervalSeconds": 2,
          "MaxAttempts": 3,
          "BackoffRate": 2
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.error",
          "Next": "HandlePipelineFailure"
        }
      ]
    },
    
    "CreateBatches": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:attic-create-batches",
      "ResultPath": "$.batches",
      "Next": "ProcessBatchesMap"
    },
    
    "ProcessBatchesMap": {
      "Type": "Map",
      "ItemsPath": "$.batches.items",
      "MaxConcurrency": 10,
      "ResultPath": "$.batchResults",
      "Iterator": {
        "StartAt": "ApifyEnrich",
        "States": {
          "ApifyEnrich": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:attic-apify-enrich",
            "Next": "MediaDownload",
            "Retry": [
              {
                "ErrorEquals": ["States.TaskFailed"],
                "IntervalSeconds": 5,
                "MaxAttempts": 3,
                "BackoffRate": 2
              }
            ]
          },
          "MediaDownload": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:attic-media-download",
            "Next": "VisionAnalysis"
          },
          "VisionAnalysis": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:attic-vision-analysis",
            "Next": "GenerateEmbedding"
          },
          "GenerateEmbedding": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:attic-embedding",
            "End": true
          }
        }
      },
      "Next": "FinalizeUpload"
    },
    
    "FinalizeUpload": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:attic-finalize",
      "Next": "SendNotification"
    },
    
    "SendNotification": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:attic-notify",
      "End": true
    },
    
    "HandlePipelineFailure": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:attic-handle-failure",
      "End": true
    }
  }
}
```

## Triggering from Upload (SQS → Lambda → Step Functions)

```python
# src/backend/lambdas/trigger_pipeline/handler.py
import boto3
import json

sfn = boto3.client('stepfunctions')

def handler(event: dict, context):
    """
    Triggered by SQS when upload completes.
    Starts Step Functions execution.
    """
    for record in event['Records']:
        body = json.loads(record['body'])
        
        execution_input = {
            "upload_id": body["upload_id"],
            "user_id": body["user_id"],
            "storage_path": body["storage_path"],
            "scope": body["scope"]
        }
        
        response = sfn.start_execution(
            stateMachineArn=os.environ['STATE_MACHINE_ARN'],
            name=f"upload-{body['upload_id']}",
            input=json.dumps(execution_input)
        )
        
        # Store execution ARN for status tracking
        # (update uploads table with step_functions_execution_arn)
```

## Local Testing with SAM

```bash
# Test single Lambda
sam local invoke ParseExportFunction \
  -e events/parse_export.json \
  --env-vars env.json

# events/parse_export.json
{
  "upload_id": "test-upload-123",
  "user_id": "test-user-456",
  "storage_path": "test-user-456/test-upload-123/export.zip",
  "scope": "liked"
}

# env.json
{
  "ParseExportFunction": {
    "SUPABASE_URL": "http://localhost:54321",
    "SUPABASE_SERVICE_ROLE_KEY": "...",
    "S3_BUCKET": "attic-dev"
  }
}
```

## Structured Logging Schema

Always include these fields:

| Field | Required | Description |
|-------|----------|-------------|
| `event` | Yes | Event type (step_start, step_complete, item_failed) |
| `upload_id` | Yes | Correlation ID for the upload |
| `step_name` | Yes | Current pipeline step |
| `user_id` | Yes | User ID (never email) |
| `cost_usd` | If applicable | Cost of this operation |
| `duration_ms` | On completion | Time taken |
| `error` | On failure | Error message |
| `error_type` | On failure | Exception class name |

```python
# Good logging
logger.info(json.dumps({
    "event": "step_complete",
    "upload_id": "abc-123",
    "step_name": "APIFY_ENRICH",
    "user_id": "user-456",
    "processed_count": 50,
    "cost_usd": 0.10,
    "duration_ms": 4523
}))

# BAD - contains PII
logger.info(f"Processed upload for user@email.com")  # NEVER DO THIS
```

## Cost Tracking

```python
async def record_cost(
    db: AsyncSession,
    upload_id: str,
    step_type: str,
    provider: str,
    units: float,
    cost_usd: float
):
    """Record cost for billing and analytics."""
    await db.execute(
        insert(ProcessingStep).values(
            upload_id=upload_id,
            step_type=step_type,
            provider=provider,
            cost_usd=cost_usd,
            cost_units=units
        ).on_conflict_do_update(
            index_elements=["upload_id", "step_type"],
            set_={"cost_usd": cost_usd, "cost_units": units}
        )
    )
```
