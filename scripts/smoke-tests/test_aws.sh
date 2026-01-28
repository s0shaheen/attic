#!/bin/bash
# Test: AWS Resources
#
# Verifies that staging AWS resources exist and are accessible:
# - Step Functions state machine
# - Lambda functions
# - SQS queues
# - S3 buckets
#
# Requires AWS CLI configured with appropriate credentials.

set -e

AWS_REGION=${AWS_REGION:-us-east-1}
ENVIRONMENT=${ENVIRONMENT:-staging}

# Check if AWS CLI is available
if ! command -v aws &> /dev/null; then
    echo "AWS CLI not installed, skipping AWS tests"
    exit 0
fi

# Check if credentials are configured
if ! aws sts get-caller-identity --region "$AWS_REGION" >/dev/null 2>&1; then
    echo "AWS credentials not configured, skipping AWS tests"
    exit 0
fi

FAILED=0

# Check Step Functions state machine
STATE_MACHINE_NAME="attic-pipeline-$ENVIRONMENT"
if aws stepfunctions describe-state-machine \
    --state-machine-arn "arn:aws:states:$AWS_REGION:$(aws sts get-caller-identity --query Account --output text):stateMachine:$STATE_MACHINE_NAME" \
    --region "$AWS_REGION" >/dev/null 2>&1; then
    if [[ "$VERBOSE" == "true" ]]; then
        echo "Step Functions state machine exists: $STATE_MACHINE_NAME"
    fi
else
    echo "Step Functions state machine not found: $STATE_MACHINE_NAME"
    FAILED=1
fi

# Check SQS queue
QUEUE_NAME="attic-upload-queue-$ENVIRONMENT"
if aws sqs get-queue-url --queue-name "$QUEUE_NAME" --region "$AWS_REGION" >/dev/null 2>&1; then
    if [[ "$VERBOSE" == "true" ]]; then
        echo "SQS queue exists: $QUEUE_NAME"
    fi
else
    echo "SQS queue not found: $QUEUE_NAME"
    FAILED=1
fi

# Check S3 bucket
BUCKET_NAME="attic-temp-media-$ENVIRONMENT"
if aws s3api head-bucket --bucket "$BUCKET_NAME" --region "$AWS_REGION" >/dev/null 2>&1; then
    if [[ "$VERBOSE" == "true" ]]; then
        echo "S3 bucket exists: $BUCKET_NAME"
    fi
else
    echo "S3 bucket not found: $BUCKET_NAME"
    FAILED=1
fi

# Check at least one Lambda function exists
LAMBDA_PREFIX="attic-$ENVIRONMENT"
lambda_count=$(aws lambda list-functions \
    --region "$AWS_REGION" \
    --query "length(Functions[?starts_with(FunctionName, \`$LAMBDA_PREFIX\`)])" \
    --output text 2>/dev/null || echo "0")

if [[ "$lambda_count" -gt 0 ]]; then
    if [[ "$VERBOSE" == "true" ]]; then
        echo "Lambda functions found: $lambda_count with prefix $LAMBDA_PREFIX"
    fi
else
    echo "No Lambda functions found with prefix: $LAMBDA_PREFIX"
    FAILED=1
fi

exit $FAILED
