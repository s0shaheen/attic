# CI/CD Setup Guide

This document describes the CI/CD pipeline for the Attic project.

## Overview

Attic uses GitHub Actions for continuous integration and deployment:

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | PR to main, push to main | Lint, test, build validation |
| `deploy-backend.yml` | Push to main (src/backend/**) | Deploy backend to Render |
| `deploy-frontend.yml` | Push to main (src/frontend/**) | Deploy frontend to Vercel |
| `deploy-lambdas.yml` | Push to main (src/lambdas/**, infra/**) | Deploy Lambdas via SAM |

## Workflows

### CI Workflow (`ci.yml`)

Runs on every pull request and push to main. Validates code quality across all components.

**Backend Job:**
- Python 3.13 setup with pip caching
- Install dependencies: `pip install -e ".[dev]"`
- Linting: `ruff check .`
- Format check: `ruff format --check .`
- Tests: `pytest tests/ -v`

**Frontend Job:**
- Node.js 20 setup with npm caching
- Install dependencies: `npm ci`
- Linting: `npm run lint`
- Type checking: `npm run typecheck`
- Tests: `npm test` (if present)
- Build: `npm run build`

**Lambdas Job:**
- Python 3.13 setup
- AWS SAM CLI installation
- Template validation: `sam validate --lint`

### Deploy Backend (`deploy-backend.yml`)

Triggers Render deployment when backend code changes.

- **Trigger:** Push to main with changes in `src/backend/**`
- **Action:** POST to Render deploy hook URL
- **Note:** Render also auto-deploys from GitHub

### Deploy Frontend (`deploy-frontend.yml`)

Documents Vercel deployment (auto-deploys from GitHub).

- **Trigger:** Push to main with changes in `src/frontend/**`
- **Action:** Documentation only (Vercel auto-deploys)
- **Note:** Can be extended to use Vercel CLI for more control

### Deploy Lambdas (`deploy-lambdas.yml`)

Deploys AWS Lambda functions using SAM.

- **Trigger:** Push to main with changes in `src/lambdas/**` or `infra/**`
- **Action:** `sam build && sam deploy`
- **Manual dispatch:** Can be triggered manually with environment selection

## Required GitHub Secrets

Add these secrets in your GitHub repository settings (Settings > Secrets and variables > Actions):

### AWS Credentials (for Lambda deployment)

| Secret | Description | Example |
|--------|-------------|---------|
| `AWS_ACCESS_KEY_ID` | AWS access key for SAM deployment | `AKIA...` |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key for SAM deployment | `wJal...` |

**IAM Policy Requirements:**
The AWS credentials need permissions to:
- Create/update CloudFormation stacks
- Create/update Lambda functions
- Create/update Step Functions state machines
- Create/update SQS queues
- Create/update S3 buckets
- Create/update IAM roles (CAPABILITY_NAMED_IAM)

### Render (optional - for backend deployment)

| Secret | Description | Example |
|--------|-------------|---------|
| `RENDER_DEPLOY_HOOK_URL` | Render service deploy hook URL | `https://api.render.com/deploy/srv-...` |

**How to get:**
1. Go to Render Dashboard > Your Service > Settings
2. Scroll to "Deploy Hook"
3. Copy the URL

### Vercel (optional - for manual frontend deployment)

| Secret | Description |
|--------|-------------|
| `VERCEL_TOKEN` | Vercel authentication token |
| `VERCEL_ORG_ID` | Vercel organization ID |
| `VERCEL_PROJECT_ID` | Vercel project ID |

**Note:** These are only needed if you want to use Vercel CLI instead of auto-deploy.

## Branch Protection Rules

Configure branch protection for the `main` branch:

1. Go to Settings > Branches > Add rule
2. Set "Branch name pattern" to `main`
3. Enable:
   - **Require a pull request before merging**
     - Require approvals: 1 (adjust as needed)
   - **Require status checks to pass before merging**
     - Status checks that are required:
       - `Backend (Python)`
       - `Frontend (Next.js)`
       - `Lambdas (SAM Validate)`
   - **Require branches to be up to date before merging**
   - **Do not allow bypassing the above settings**

## Dependabot

Dependabot is configured to check for dependency updates weekly:

- **Python (pip):** `src/backend/` - Monday 9 AM ET
- **npm:** `src/frontend/` - Monday 9 AM ET
- **GitHub Actions:** `/` - Monday 9 AM ET

Minor and patch updates are grouped together to reduce PR noise.

## Troubleshooting

### CI Failing on PR

1. **Linting errors:** Run locally:
   ```bash
   cd src/backend && ruff check . && ruff format .
   cd src/frontend && npm run lint
   ```

2. **Test failures:** Run locally:
   ```bash
   cd src/backend && pytest tests/ -v
   cd src/frontend && npm test
   ```

3. **Type errors:** Run locally:
   ```bash
   cd src/frontend && npm run typecheck
   ```

4. **Build failures:** Run locally:
   ```bash
   cd src/frontend && npm run build
   ```

### Lambda Deployment Failing

1. **Check AWS credentials:** Ensure `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are set correctly
2. **Check IAM permissions:** Ensure the IAM user has sufficient permissions
3. **Check SAM template:** Run `sam validate --lint` locally
4. **Check CloudFormation:** View stack events in AWS Console for detailed errors

### Backend Not Deploying

1. **Check Render dashboard:** Manual deployment may be needed on first setup
2. **Check deploy hook:** Ensure `RENDER_DEPLOY_HOOK_URL` is set (optional)
3. **Check Render logs:** View logs in Render Dashboard for deployment errors

## Local Development

Before pushing, run the same checks locally:

```bash
# Backend
cd src/backend
ruff check .
ruff format --check .
pytest tests/ -v

# Frontend
cd src/frontend
npm run lint
npm run typecheck
npm test
npm run build

# Lambdas
cd infra
sam validate --lint
sam build
```
