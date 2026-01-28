# AWS Infrastructure Setup

## Prerequisites

- **AWS CLI** v2: `aws configure` with appropriate credentials
- **SAM CLI**: Install via `brew install aws-sam-cli` (macOS) or [official docs](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
- **Docker**: Required for `sam local invoke` and `sam local start-api`
- **Python 3.12**: Required for Lambda runtime

## Resource Naming Convention

All resources follow the pattern: `attic-{service}-{environment}`

| Resource Type | Name Pattern | Example |
|---|---|---|
| S3 Bucket | `attic-temp-media-{env}` | `attic-temp-media-dev` |
| SQS Queue | `attic-upload-queue-{env}` | `attic-upload-queue-dev` |
| State Machine | `attic-video-processing-{env}` | `attic-video-processing-dev` |
| Lambda Function | `attic-{step}-{env}` | `attic-parse-export-dev` |
| IAM Role | `attic-{service}-{env}` | `attic-lambda-execution-dev` |
| Log Group | `/aws/lambda/attic-{step}-{env}` | `/aws/lambda/attic-parse-export-dev` |

## Deployment Commands

### Validate Template

```bash
cd infra
sam validate
```

### Build

```bash
cd infra
sam build
```

### Deploy (First Time - Guided)

```bash
cd infra
sam deploy --guided
```

This will prompt for parameters and save configuration to `samconfig.toml`.

### Deploy (Subsequent)

```bash
cd infra
sam deploy
```

Uses saved configuration from `samconfig.toml`.

### Deploy to Specific Environment

```bash
cd infra
sam deploy --parameter-overrides Environment=staging
```

### Delete Stack

```bash
cd infra
sam delete --stack-name attic-staging
```

## Local Testing

### Invoke a Lambda Locally

```bash
cd infra
sam local invoke ParseExportFunction --event '{"upload_id": "test-uuid", "user_id": "user-uuid"}'
```

### Test Step Functions Locally

Use the AWS Step Functions Local (Docker-based) or test individual Lambdas:

```bash
# Test each stub returns expected format
sam local invoke ApifyEnrichFunction --event '{"upload_id": "test"}'
sam local invoke MediaDownloadFunction --event '{"upload_id": "test"}'
```

## Architecture Overview

### Processing Pipeline Flow

```
SQS Upload Queue
       |
       v
ParseExport (Lambda)
       |
       v
EnrichBatch (Map State, 10x concurrent)
   └── ApifyEnrich (Lambda, batches of 50 URLs)
       |
       v
ProcessVideos (Map State, 5x concurrent)
   ├── MediaDownload (Lambda)
   ├── SubtitleFetch (Lambda)
   ├── WhisperTranscribe (Lambda, conditional)
   ├── VisionAnalysis (Lambda)
   └── Embedding (Lambda)
       |
       v
TextFusion (Lambda)
       |
       v
DerivedFields (Lambda)
       |
       v
UpdateSearchIndex (Lambda)
       |
       v
FinalizeUpload (Pass State)
```

### Error Handling

- Each state has a **Retry** policy: 3 attempts, 2x exponential backoff
- Each state has a **Catch** block routing to `HandleError`
- HandleError Lambda logs failures and marks affected videos as failed
- SQS DLQ captures messages that fail after max retries

### Idempotency

All Lambda functions MUST be idempotent:

- Use `common.idempotency.generate_idempotency_key(upload_id, video_url)` for deterministic keys
- Use database upserts for all writes
- Check `processing_state` before re-processing

## Tags

All resources are tagged with:

- `project: attic`
- `environment: {dev|staging|prod}`

## Costs (Estimated Monthly - Dev)

| Service | Estimated Cost |
|---|---|
| Lambda (stub calls) | ~$0.00 |
| Step Functions | ~$0.00 |
| SQS | ~$0.00 |
| S3 (temp storage, 7-day lifecycle) | ~$0.01 |
| CloudWatch Logs | ~$0.50 |
| **Total** | **~$0.51** |

Production costs will vary based on upload volume and processing complexity.
