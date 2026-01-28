# Staging Environment Setup

This document describes the staging environment configuration for Attic.

## Overview

The staging environment mirrors production and is used for:
- Pre-production testing
- Integration testing with real external services
- Smoke testing after deployments
- QA validation before production releases

## Architecture

| Component | Staging Service |
|-----------|-----------------|
| Frontend | Vercel (staging branch) |
| Backend API | Render (staging service) |
| Database | Supabase (staging project) |
| AWS Lambda | AWS (staging stack) |
| Step Functions | AWS (staging stack) |

## AWS Resources

The staging AWS infrastructure is deployed via SAM using `infra/staging/samconfig.toml`:

```bash
# Deploy from infra/ directory
sam build --use-container
sam deploy --config-file staging/samconfig.toml
```

### Resource Naming Convention

All staging resources use the `-staging` suffix:
- Stack: `attic-staging`
- S3 Bucket: `attic-temp-media-staging`
- SQS Queue: `attic-upload-queue-staging`
- State Machine: `attic-pipeline-staging`
- Lambda Functions: `attic-staging-*`

## Environment Variables

### Backend (Render)

Required environment variables for the staging backend:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Supabase PostgreSQL connection string |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anonymous key |
| `SUPABASE_SERVICE_KEY` | Supabase service role key |
| `AWS_ACCESS_KEY_ID` | AWS credentials for S3/SQS access |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials |
| `AWS_REGION` | `us-east-1` |
| `OPENAI_API_KEY` | OpenAI API key for AI features |
| `APIFY_API_KEY` | Apify API key for TikTok metadata |
| `STRIPE_SECRET_KEY` | Stripe secret key (test mode) |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret |
| `RESEND_API_KEY` | Resend API key for emails |
| `SENTRY_DSN` | Sentry DSN for error tracking |
| `ENVIRONMENT` | `staging` |

### Frontend (Vercel)

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anonymous key |
| `NEXT_PUBLIC_API_URL` | Backend API URL |
| `NEXT_PUBLIC_POSTHOG_KEY` | PostHog project key |
| `NEXT_PUBLIC_SENTRY_DSN` | Sentry DSN |

### GitHub Actions Secrets

Required secrets for CI/CD deployment:

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | AWS deployment credentials |
| `AWS_SECRET_ACCESS_KEY` | AWS deployment credentials |
| `RENDER_STAGING_DEPLOY_HOOK_URL` | Render deploy hook URL |
| `STAGING_BACKEND_URL` | Backend URL for smoke tests |
| `STAGING_FRONTEND_URL` | Frontend URL for smoke tests |
| `STAGING_SUPABASE_URL` | Supabase URL for smoke tests |
| `STAGING_SUPABASE_ANON_KEY` | Supabase key for smoke tests |
| `STAGING_TEST_USER_EMAIL` | Test user email |
| `STAGING_TEST_USER_PASSWORD` | Test user password |

## Deployment

### Automatic Deployment

Staging deployments are triggered automatically on push to `main` via `.github/workflows/deploy-staging.yml`.

The deployment workflow:
1. Builds and deploys Lambda functions via SAM
2. Triggers Render backend deployment
3. Runs smoke tests (can be skipped via workflow dispatch)
4. Notifies on success/failure

### Manual Deployment

To manually trigger a staging deployment:

```bash
# Via GitHub CLI
gh workflow run deploy-staging.yml

# Skip smoke tests
gh workflow run deploy-staging.yml -f skip_smoke_tests=true
```

### SAM Deployment

To deploy AWS resources manually:

```bash
cd infra

# Build with container (ensures consistent environment)
sam build --use-container

# Deploy to staging
sam deploy --config-file staging/samconfig.toml

# Deploy with confirmation prompts
sam deploy --config-file staging/samconfig.toml --confirm-changeset
```

## Smoke Tests

Smoke tests verify basic functionality after deployment. Located in `scripts/smoke-tests/`.

### Running Smoke Tests

```bash
# Run all tests
./scripts/smoke-tests/run.sh --env staging

# Run with verbose output
VERBOSE=true ./scripts/smoke-tests/run.sh --env staging

# Run specific test
./scripts/smoke-tests/test_health.sh
```

### Test Suite

| Test | Description |
|------|-------------|
| `test_health.sh` | Backend health endpoint |
| `test_frontend.sh` | Frontend accessibility |
| `test_supabase.sh` | Supabase connection |
| `test_aws.sh` | AWS resource verification |
| `test_auth.sh` | Authentication flow |
| `test_upload.sh` | Upload endpoint |

### Required Environment Variables

```bash
export STAGING_BACKEND_URL="https://attic-staging.onrender.com"
export STAGING_FRONTEND_URL="https://attic-staging.vercel.app"
export STAGING_SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_ANON_KEY="your-anon-key"
export TEST_USER_EMAIL="test@example.com"
export TEST_USER_PASSWORD="test-password"
export AWS_REGION="us-east-1"
```

## Monitoring

### Logs

- **Backend**: Render dashboard > Logs
- **Frontend**: Vercel dashboard > Deployments > Logs
- **Lambda**: AWS CloudWatch > Log groups > `/aws/lambda/attic-staging-*`
- **Step Functions**: AWS Console > Step Functions > Executions

### Error Tracking

- Sentry project: `attic-staging`
- Alerts configured for error rate spikes

### Metrics

- PostHog dashboard for user analytics
- AWS CloudWatch for Lambda metrics
- Render metrics for backend performance

## Troubleshooting

### Common Issues

**Smoke tests failing on auth:**
- Verify `STAGING_SUPABASE_URL` and `SUPABASE_ANON_KEY` are correct
- Ensure test user exists in Supabase Auth

**Lambda deployment fails:**
- Check AWS credentials have sufficient permissions
- Verify S3 bucket for SAM artifacts exists
- Review CloudFormation events for detailed errors

**Backend not responding:**
- Check Render service status
- Verify environment variables are set
- Review Render logs for startup errors

**Step Functions not executing:**
- Verify IAM roles have correct permissions
- Check SQS queue exists and has correct policies
- Review execution history for error details

### Rollback

To rollback a staging deployment:

```bash
# AWS (via CloudFormation)
aws cloudformation rollback-stack --stack-name attic-staging

# Or redeploy previous version
git checkout <previous-commit>
sam build --use-container
sam deploy --config-file staging/samconfig.toml
```

For Render and Vercel, use their respective dashboards to rollback to previous deployments.
