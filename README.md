# Attic

> Personal analytics platform for TikTok data — understanding your digital footprint through AI-powered enrichment.

**This project has been archived.** See [ARCHIVED.md](ARCHIVED.md) for details and [portable-ai-data-kit](https://github.com/s0shaheen/portable-ai-data-kit) for the successor project.

---

## Architecture

```
                         Attic — System Architecture

  Browser                    API                        AWS
 ┌─────────────────┐   ┌─────────────┐   ┌──────────────────────────────┐
 │                  │   │             │   │  Step Functions              │
 │  Next.js 14      │   │  FastAPI    │   │  ┌────────────────────────┐  │
 │  ├─ Auth (OAuth) ├──►│  ├─ Auth    ├──►│  │ 1. Parse Export        │  │
 │  ├─ Upload (Uppy)│   │  ├─ Upload  │   │  │ 2. Apify Enrich       │  │
 │  ├─ Library      │   │  ├─ Search  │   │  │ 3. Media Download     │  │
 │  └─ Search       │   │  └─ User    │   │  │ 4. Subtitle Fetch     │  │
 │                  │   │             │   │  │ 5. Whisper Transcribe  │  │
 └────────┬─────────┘   └──────┬──────┘   │  │ 6. Vision Analysis    │  │
          │                    │           │  │ 7. Text Fusion        │  │
          │   Supabase         │           │  │ 8. Embedding          │  │
          │  ┌─────────────────┤           │  │ 9. Derived Fields     │  │
          │  │ Auth (JWT)      │           │  │10. Search Index       │  │
          ├─►│ Storage (Blobs) │           │  └────────────────────────┘  │
          │  │ PostgreSQL +    │           │         │                    │
          │  │   pgvector      │◄──────────┤  S3 (temp) │ SQS (DLQ)     │
          │  │ Realtime (WS)   │           └──────────────────────────────┘
          │  └─────────────────┘
          │
  Vercel (hosting)
```

## What Was Built

| Component | Description | Status |
|-----------|-------------|--------|
| **TikTok Parser** | Security-hardened ZIP export parser (634 lines) — zip-slip defense, path traversal prevention, multiple format variations | Production-ready |
| **Authentication** | JWT validation (HS256 + ES256), Supabase JWKS, Google OAuth, session middleware | Complete |
| **Upload Pipeline** | Drag-and-drop upload, presigned URLs, validation, scope selection, consent flow | Complete |
| **Database Schema** | 5 Alembic migrations, 70+ fields per media event, pgvector embeddings, RLS policies | Complete |
| **User Deletion** | GDPR-compliant cascade — storage files, Supabase Auth, confirmation email | Complete |
| **Frontend** | Auth flow, upload flow, settings, error handling — Next.js + shadcn/ui | Complete |
| **Lambda Stubs** | 10 pipeline handlers + error handler, shared logger + idempotency decorator | Scaffolded |
| **Infrastructure** | SAM template, Step Functions state machine, S3 lifecycle, SQS + DLQ, Docker Compose | Scaffolded |
| **Processing Pipeline** | Apify enrichment, Whisper transcription, GPT-4 Vision, embeddings, search indexing | Not started |

**23 of ~78 total tasks completed (Epics 0-2).** Epic 3 (processing pipeline) was next.

## Test Coverage

| Area | Tests | Notes |
|------|-------|-------|
| Backend unit | ~60 | Auth (17 JWT cases), parser (15 format variations), uploads, validation, consent, GDPR deletion, models |
| Frontend | ~30 | Uppy uploader (20 cases), API client, Supabase client/server/middleware, hooks |
| Test fixtures | — | Synthetic TikTok exports (~13K lines each), edge case slices, anonymized data, generation tools |
| Pipeline stubs | ~29 files | Test structure defined with `pytest.skip()` for all 10 Lambda steps |

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Frontend** | Next.js 14, TypeScript, Tailwind, shadcn/ui, TanStack Query, Uppy |
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic |
| **Database** | Supabase PostgreSQL + pgvector, Alembic migrations |
| **Auth** | Supabase Auth (Google OAuth), JWT validation |
| **Workflow** | AWS Step Functions, Lambda, SQS |
| **AI/Enrichment** | Apify (metadata), OpenAI (vision, transcription, embeddings) |
| **Infrastructure** | AWS SAM, Docker Compose, Vercel, Render |

## Documentation

| Document | Path |
|----------|------|
| Product Requirements (v1.3.0) | [`docs/MVP/PRD/Attic_MVP_PRD_v1.3.0.md`](docs/MVP/PRD/Attic_MVP_PRD_v1.3.0.md) |
| Dev Guide (v1.3.0) | [`docs/MVP/tasks/Attic_MVP_Dev_Guide_v1.3.0.md`](docs/MVP/tasks/Attic_MVP_Dev_Guide_v1.3.0.md) |
| Task Specs (37 specs) | [`docs/MVP/tasks/specs/`](docs/MVP/tasks/specs/) |
| Architecture Decisions | [`docs/MVP/ADR/`](docs/MVP/ADR/) |
| Setup Guides (7 guides) | [`docs/setup/`](docs/setup/) |
| Repository Status | [`docs/REPO_STATUS.md`](docs/REPO_STATUS.md) |

## Why Archived

Attic was a learning-intensive project that validated several ideas but grew beyond practical scope for a solo project:

1. **Infrastructure cost** — 10 Lambda functions, OpenAI API calls, Apify scraping, S3 storage, and Supabase all running adds up fast
2. **Maintenance burden** — TikTok export formats change without notice; keeping the parser current requires ongoing effort
3. **Narrower opportunity** — The most reusable piece (parsing messy platform exports into clean data) works better as a standalone tool

The data parsing work continues in [portable-ai-data-kit](https://github.com/s0shaheen/portable-ai-data-kit).

## Successor Project

**[portable-ai-data-kit](https://github.com/s0shaheen/portable-ai-data-kit)** extracts the core insight from Attic — turning platform data exports into AI-ready datasets — into a focused, open-source CLI tool. No cloud infrastructure required.

<details>
<summary><strong>Running Locally</strong></summary>

### Prerequisites

- Python 3.12+
- Node.js 18+
- Docker (for LocalStack and Supabase)
- AWS SAM CLI

### Backend

```bash
cd src/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Lint + format
ruff check . && ruff format .

# Database migrations
alembic upgrade head
```

### Frontend

```bash
cd src/frontend
npm install

# Dev server
npm run dev

# Tests, lint, typecheck
npm test
npm run lint
npm run typecheck
```

### Infrastructure

```bash
# Start local Supabase
supabase start

# Start LocalStack (S3, SQS, Step Functions)
docker compose up -d

# Test Lambda locally
sam local invoke FunctionName
```

See [`docs/setup/`](docs/setup/) for detailed guides on AWS, Supabase, environment variables, staging, CI/CD, and storage configuration.

</details>

---

*Archived Q1 2026 by [@s0shaheen](https://github.com/s0shaheen)*
