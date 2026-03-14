# Attic

> Personal analytics platform for TikTok data — understanding your digital footprint through AI-powered enrichment.

Upload your TikTok data export, and Attic enriches each media item with metadata, visual analysis, transcription, and semantic tagging — turning raw platform data into searchable, structured insights.

## Architecture

```
  Browser                    API                        AWS
 ┌─────────────────┐   ┌─────────────┐   ┌──────────────────────────────┐
 │                  │   │             │   │  Step Functions              │
 │  Next.js 16      │   │  FastAPI    │   │  ┌────────────────────────┐  │
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

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Frontend** | Next.js 16, TypeScript, Tailwind, shadcn/ui, TanStack Query, Uppy |
| **Backend** | Python 3.13, FastAPI, SQLAlchemy 2.0, Pydantic |
| **Database** | Supabase PostgreSQL + pgvector, Alembic migrations |
| **Auth** | Supabase Auth (Google OAuth), JWT (HS256 + ES256) |
| **Workflow** | AWS Step Functions, Lambda, SQS |
| **AI/Enrichment** | Apify (metadata), OpenAI (vision, transcription, embeddings) |
| **Observability** | Sentry (errors), PostHog (analytics) |
| **Infrastructure** | Vercel, Render, AWS SAM, Docker Compose |

## Status

| Epic | Name | Progress |
|------|------|----------|
| 0 | Infrastructure & Foundation | 9/9 |
| 1 | Authentication | 6/6 |
| 2 | Upload & Consent | 8/8 |
| 3 | Processing Pipeline | 0/15 |
| 4 | Progress & Notifications | 0/5 |
| 5 | Library View | 0/7 |
| 6 | Search | 0/6 |
| 7 | Detail View | 0/5 |
| 8 | User Settings & Landing | 0/7 |
| 9 | Production Readiness | 0/10 |

**23/78 tasks complete.** Currently working on Epic 3 — the 10-step processing pipeline.

See [docs/REPO_STATUS.md](docs/REPO_STATUS.md) for detailed implementation status.

## Getting Started

### Prerequisites

- Docker Desktop 4.0+
- Supabase CLI 1.0+
- Node.js 20+
- Python 3.13+

### Quick Start

```bash
# Start backend + local infrastructure
./scripts/dev-start.sh

# Start frontend
cd src/frontend && npm install && npm run dev
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| Supabase Studio | http://localhost:54323 |
| LocalStack | http://localhost:4566 |

See [docs/setup/](docs/setup/) for detailed guides on [local dev](docs/setup/local-dev.md), [AWS](docs/setup/aws.md), [Supabase](docs/setup/supabase.md), [environment variables](docs/setup/environment.md), [staging](docs/setup/staging.md), and [CI/CD](docs/setup/ci-cd.md).

## Development

```bash
# Backend (from src/backend/)
pytest tests/ -v                    # Run all tests
ruff check . && ruff format .       # Lint + format
alembic upgrade head                # Run migrations

# Frontend (from src/frontend/)
npm test                            # Run tests
npm run lint                        # Lint
npm run typecheck                   # Type check
npm run build                       # Production build
```

## Testing

60+ unit tests across backend and frontend, with synthetic TikTok export fixtures for deterministic testing.

```bash
# Backend
cd src/backend
.venv/bin/python -m pytest -v       # 231 passing, 674 skipped (Epic 3+ stubs)

# Frontend
cd src/frontend
npm test
```

Test fixtures at `tests/fixtures/tiktok-exports/` include synthetic user data (~13K lines each), edge case slices, and generation tools.

## Documentation

| Document | Description |
|----------|-------------|
| [PRD v1.3.0](docs/MVP/PRD/Attic_MVP_PRD_v1.3.0.md) | Product spec, data model, API contracts |
| [Dev Guide v1.3.0](docs/MVP/tasks/Attic_MVP_Dev_Guide_v1.3.0.md) | Epic/task breakdown with status |
| [Task Specs](docs/MVP/tasks/specs/) | 37 individual task specifications |
| [ADRs](docs/MVP/ADR/) | Architecture decision records |
| [Setup Guides](docs/setup/) | 7 guides (local dev, AWS, Supabase, env, staging, CI/CD, storage) |

## Processing Pipeline

10-step async pipeline orchestrated by AWS Step Functions:

1. **Parse Export** — Extract URLs from ZIP, create `media_event` rows
2. **Apify Enrich** — Fetch TikTok metadata (batched, 50/call)
3. **Media Download** — Download video/images to S3 temp
4. **Subtitle Fetch** — Get subtitles if available
5. **Whisper Transcribe** — Transcribe via OpenAI if no subtitles
6. **Vision Analysis** — GPT-4 Vision tagging (batched, 5 images/call)
7. **Text Fusion** — Combine caption + hashtags + transcript + OCR + visual tags
8. **Embedding** — Generate 1536-dim vectors (batched, 100/call)
9. **Derived Fields** — Compute engagement rate, interaction hour, etc.
10. **Search Index** — Update full-text (GIN) + vector (ivfflat) indexes

Every Lambda function is idempotent — safe under retries via upserts and deterministic IDs.
