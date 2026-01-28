#!/bin/bash
# Attic LocalStack Initialization Script
# This script runs automatically when LocalStack starts
#
# Creates:
# - S3 bucket: attic-temp-media
# - SQS queue: attic-upload-queue
# - SQS dead-letter queue: attic-upload-queue-dlq

set -e

echo "==> Initializing Attic AWS resources in LocalStack..."

# Wait for LocalStack to be fully ready
echo "Waiting for LocalStack services..."
sleep 2

# ---------- S3 Bucket ----------
echo "Creating S3 bucket: attic-temp-media"
awslocal s3 mb s3://attic-temp-media 2>/dev/null || echo "Bucket already exists"

# Set bucket lifecycle (expire objects after 7 days, matching production)
awslocal s3api put-bucket-lifecycle-configuration \
    --bucket attic-temp-media \
    --lifecycle-configuration '{
        "Rules": [{
            "ID": "ExpireTemp",
            "Status": "Enabled",
            "Filter": {"Prefix": ""},
            "Expiration": {"Days": 7}
        }]
    }' 2>/dev/null || echo "Lifecycle configuration already set"

echo "S3 bucket created successfully"

# ---------- SQS Dead Letter Queue ----------
echo "Creating SQS dead-letter queue: attic-upload-queue-dlq"
DLQ_URL=$(awslocal sqs create-queue \
    --queue-name attic-upload-queue-dlq \
    --attributes MessageRetentionPeriod=1209600 \
    --query 'QueueUrl' \
    --output text 2>/dev/null) || DLQ_URL=$(awslocal sqs get-queue-url --queue-name attic-upload-queue-dlq --query 'QueueUrl' --output text)

DLQ_ARN=$(awslocal sqs get-queue-attributes \
    --queue-url "$DLQ_URL" \
    --attribute-names QueueArn \
    --query 'Attributes.QueueArn' \
    --output text)

echo "DLQ ARN: $DLQ_ARN"

# ---------- SQS Main Queue ----------
echo "Creating SQS queue: attic-upload-queue"
awslocal sqs create-queue \
    --queue-name attic-upload-queue \
    --attributes '{
        "VisibilityTimeout": "960",
        "MessageRetentionPeriod": "1209600",
        "DelaySeconds": "0",
        "RedrivePolicy": "{\"deadLetterTargetArn\":\"'"$DLQ_ARN"'\",\"maxReceiveCount\":\"3\"}"
    }' 2>/dev/null || echo "Queue already exists"

echo "SQS queues created successfully"

# ---------- Verification ----------
echo ""
echo "==> Verification:"
echo "S3 Buckets:"
awslocal s3 ls

echo ""
echo "SQS Queues:"
awslocal sqs list-queues

echo ""
echo "==> LocalStack initialization complete!"
echo ""
echo "Endpoints:"
echo "  S3:             http://localhost:4566"
echo "  SQS:            http://localhost:4566"
echo "  Step Functions: http://localhost:4566"
echo "  Lambda:         http://localhost:4566"
echo ""
echo "Test commands:"
echo "  awslocal s3 ls"
echo "  awslocal sqs list-queues"
echo "  awslocal stepfunctions list-state-machines"
