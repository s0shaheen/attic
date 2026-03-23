# Production Deployment

Checklist for deploying Attic to production. Prerequisites: Supabase production project, Vercel account, Render account.

## DNS

- `attic.to` → Vercel (frontend)
- `api.attic.to` → Render (backend)
- Configure both in your DNS provider

## Supabase (Production Project)

- [ ] Create production project at supabase.com
- [ ] Enable Google OAuth: Authentication → Providers → Google
- [ ] Set redirect URLs: `https://attic.to/auth/callback`
- [ ] Enable Email/Password auth for admin access
- [ ] Run migrations: `supabase db push --linked`
- [ ] Enable RLS on all tables
- [ ] Copy keys: Project Settings → API → `anon` key, `service_role` key, JWT secret

## Frontend (Vercel)

- [ ] Create Vercel project linked to this repo
- [ ] Set root directory: `src/frontend`
- [ ] Set environment variables:
  - `NEXT_PUBLIC_SUPABASE_URL` — production Supabase URL
  - `NEXT_PUBLIC_SUPABASE_ANON_KEY` — production anon key
  - `NEXT_PUBLIC_API_URL` — `https://api.attic.to`
  - `NEXT_PUBLIC_ENVIRONMENT` — `production`
  - `NEXT_PUBLIC_POSTHOG_KEY` — PostHog project key
  - `NEXT_PUBLIC_SENTRY_DSN` — Sentry DSN
- [ ] Deploy: `git push` triggers auto-deploy

## Backend (Render)

- [ ] Create Render web service linked to this repo
- [ ] Set root directory: `src/backend`
- [ ] Set all env vars from `.env.master.example` with production values
- [ ] Key differences from dev:
  - `DATABASE_URL` — production Supabase connection string (connection pooler)
  - `SUPABASE_URL` — production URL
  - `SUPABASE_SECRET_KEY` — production service role key
  - `STRIPE_SECRET_KEY` — live key (not `sk_test_`)
  - `AWS_ENDPOINT_URL` — remove (use real AWS, not LocalStack)
  - `ENVIRONMENT` — `production`
  - `LOG_LEVEL` — `INFO`
  - `CORS_ORIGINS` — `https://attic.to`
- [ ] Deploy: `git push` triggers auto-deploy

## AWS (Pipeline)

- [ ] Create SQS queue for upload processing
- [ ] Deploy Lambda via SAM: `sam deploy --guided`
- [ ] Set `SQS_QUEUE_URL` in Render env vars

## Post-Deploy

- [ ] Verify health check: `curl https://api.attic.to/health`
- [ ] Test Google OAuth flow end-to-end
- [ ] Test file upload → pipeline → chat query
- [ ] Verify Sentry receives errors
- [ ] Verify PostHog receives events
