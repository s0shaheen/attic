# Environment Configuration

This document describes all environment variables required to run Attic.

## Quick Start

1. Copy the example files:
   ```bash
   cp .env.example .env
   cp src/backend/.env.example src/backend/.env
   cp src/frontend/.env.example src/frontend/.env.local
   ```

2. Fill in the values following the guide below.

---

## Backend Variables (`src/backend/.env`)

### Database

| Variable | Required | Description | Where to Get |
|----------|----------|-------------|--------------|
| `DATABASE_URL` | Yes | PostgreSQL connection URL | Supabase Dashboard → Settings → Database → Connection string (use "URI" format with `asyncpg`) |
| `SUPABASE_URL` | Yes | Supabase project URL | Supabase Dashboard → Settings → API → Project URL |
| `SUPABASE_SERVICE_KEY` | Yes | Service role key (server-side only) | Supabase Dashboard → Settings → API → Service role key |

**Example:**
```
DATABASE_URL=postgresql+asyncpg://postgres:[password]@db.xxx.supabase.co:5432/postgres
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### AWS

| Variable | Required | Description | Where to Get |
|----------|----------|-------------|--------------|
| `AWS_ACCESS_KEY_ID` | Yes | AWS access key | AWS IAM Console → Users → Security credentials |
| `AWS_SECRET_ACCESS_KEY` | Yes | AWS secret key | AWS IAM Console (shown once on creation) |
| `AWS_REGION` | No | AWS region (default: us-east-1) | Choose your preferred region |
| `AWS_ENDPOINT_URL` | No | Override endpoint (for LocalStack) | Set to `http://localhost:4566` for local dev |

### Third-Party APIs

| Variable | Required | Description | Where to Get |
|----------|----------|-------------|--------------|
| `APIFY_API_TOKEN` | Yes | Apify API token | [Apify Console](https://console.apify.com/) → Settings → Integrations |
| `OPENAI_API_KEY` | Yes | OpenAI API key | [OpenAI Platform](https://platform.openai.com/) → API keys |

### Payments

| Variable | Required | Description | Where to Get |
|----------|----------|-------------|--------------|
| `STRIPE_SECRET_KEY` | Yes | Stripe secret key | [Stripe Dashboard](https://dashboard.stripe.com/) → Developers → API keys |
| `STRIPE_WEBHOOK_SECRET` | Yes | Webhook signing secret | Stripe Dashboard → Developers → Webhooks → Signing secret |

**Note:** Use `sk_test_*` keys for development/staging, `sk_live_*` for production.

### Notifications

| Variable | Required | Description | Where to Get |
|----------|----------|-------------|--------------|
| `RESEND_API_KEY` | Yes | Resend API key | [Resend Dashboard](https://resend.com/) → API Keys |

### Observability

| Variable | Required | Description | Where to Get |
|----------|----------|-------------|--------------|
| `SENTRY_DSN` | No | Sentry DSN for error tracking | [Sentry](https://sentry.io/) → Project Settings → Client Keys |
| `POSTHOG_API_KEY` | No | PostHog API key | [PostHog](https://posthog.com/) → Project Settings → Project API Key |

### Application

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENVIRONMENT` | No | development | `development`, `staging`, or `production` |
| `LOG_LEVEL` | No | INFO | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `CORS_ORIGINS` | No | http://localhost:3000 | Comma-separated list of allowed origins |

---

## Frontend Variables (`src/frontend/.env.local`)

All frontend variables must be prefixed with `NEXT_PUBLIC_` to be accessible in the browser.

| Variable | Required | Description | Where to Get |
|----------|----------|-------------|--------------|
| `NEXT_PUBLIC_SUPABASE_URL` | Yes | Supabase project URL | Same as backend `SUPABASE_URL` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Yes | Supabase anon key (client-safe) | Supabase Dashboard → Settings → API → anon key |
| `NEXT_PUBLIC_API_URL` | Yes | Backend API URL | `http://localhost:8000` for local dev |
| `NEXT_PUBLIC_POSTHOG_KEY` | No | PostHog project key | PostHog → Project Settings |
| `NEXT_PUBLIC_SENTRY_DSN` | No | Sentry DSN | Same as backend |
| `NEXT_PUBLIC_ENVIRONMENT` | No | Environment name | `development`, `staging`, `production` |

**Security Note:** Never put secret keys in `NEXT_PUBLIC_*` variables. They are exposed to the browser.

---

## Lambda Variables

Lambda environment variables are configured in the SAM template (`infra/template.yaml`), not in `.env` files. See `src/lambdas/.env.example` for reference.

---

## Local Development

Default: Supabase Cloud (always on, no Docker needed for database).
Optional: Local Supabase via `supabase start` for migration work or full resets.

```bash
# Cloud (default) — values come from .env.master → setup-env.sh
DATABASE_URL=postgresql+asyncpg://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
SUPABASE_URL=https://[PROJECT-REF].supabase.co
SUPABASE_SECRET_KEY=<from Supabase Dashboard → Settings → API>
SUPABASE_PUBLISHABLE_KEY=<from Supabase Dashboard → Settings → API>

# Local Supabase (optional) — run `supabase start` first
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:54322/postgres
# SUPABASE_URL=http://localhost:54321
# SUPABASE_SECRET_KEY=<from supabase start output>
# SUPABASE_PUBLISHABLE_KEY=<from supabase start output>

# LocalStack for AWS (optional, requires Docker)
AWS_ENDPOINT_URL=http://localhost:4566
```

---

## Environment-Specific Values

| Environment | CORS_ORIGINS | LOG_LEVEL | Notes |
|-------------|--------------|-----------|-------|
| development | http://localhost:3000 | DEBUG | LocalStack, local Supabase |
| staging | https://staging.attic.app | INFO | Test Stripe keys |
| production | https://attic.app | WARNING | Live Stripe keys |

---

## Secrets Management

**Never commit secrets to git.** The following files are in `.gitignore`:
- `.env`
- `.env.local`
- `.env.*.local`
- `src/backend/.env`
- `src/frontend/.env.local`

For CI/CD and production, use:
- GitHub Secrets (for GitHub Actions)
- Vercel Environment Variables (for frontend)
- Render Environment Variables (for backend)
- AWS SSM Parameter Store (for Lambda functions)
