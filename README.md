# Attic

> Personal content intelligence for your saved TikTok videos.

Upload your TikTok data export and Attic turns it into a searchable, classified library you can explore through natural conversation. Every video is classified across 8 semantic facets, embedded for similarity search, and made accessible through an agentic chat interface.

## Features

- **Agentic chat** — ask questions about your saved content in natural language and get specific, sourced answers
- **8-facet classification** — every video is tagged across affect, topic, genre, intent, creator role, viewer orientation, presentation style, and provenance
- **Semantic search** — find similar content using pgvector cosine similarity over 1536-dim embeddings
- **Visual analysis** — Gemini Flash analyzes thumbnails with Google Search grounding for richer context
- **Entity resolution** — automatically links mentions to Google Maps, Google Books, TMDB, and Spotify
- **TikTok data import** — upload your data export ZIP and a 4-step pipeline handles the rest
- **Real-time streaming** — agent responses stream over SSE as they're generated

## Getting Started

### Prerequisites

- Python 3.13+ with [uv](https://docs.astral.sh/uv/)
- Node.js 20+
- Supabase CLI (`brew install supabase/tap/supabase`)
- Docker Desktop (optional — only needed for LocalStack pipeline testing)

### Setup

```bash
git clone https://github.com/s0shaheen/attic.git
cd attic

# Configure environment
cp .env.master.example .env.master   # Fill in your API keys
./scripts/setup-env.sh               # Generates derived .env files

# Install dependencies
cd src/backend && uv sync --all-extras && cd ../..
cd src/frontend && npm install && cd ../..

# Run database migrations
cd src/backend && ../../.venv/bin/alembic upgrade head && cd ../..
```

### Running Locally

```bash
# Full stack
./scripts/dev-start.sh

# Or run services individually
cd src/backend && ../../.venv/bin/uvicorn app.main:app --port 8000 --reload  # API
cd src/frontend && npm run dev                                                # UI
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |

> [!TIP]
> **Test login:** `test@attic.to` / `testpassword123` — pre-loaded with sample media events.

> [!NOTE]
> Supabase Cloud is always on — no Docker needed for the database. Pass `--with-localstack` to `dev-start.sh` if you need S3/SQS pipeline testing locally.

## Architecture

```
Browser (Next.js 14) ──SSE──► FastAPI ──► Agent Loop (Claude Haiku 4.5)
                                            ├─ query_items (SQLAlchemy)
                                            ├─ classify (Gemini Flash)
                                            ├─ analyze_visual (Gemini Flash + grounding)
                                            ├─ search_similar (pgvector cosine)
                                            ├─ get_stats (aggregate queries)
                                            └─ resolve_entity (Maps/Books/TMDB/Spotify)
                                          All results cached → media_events DB

SQS → Lambda: parse_export → apify_enrich → subtitle_fetch → embed
               (runs once per upload, 4 sequential steps)
```

### Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Frontend** | Next.js 14 (App Router), TypeScript, Tailwind, shadcn/ui, React 19, TanStack Query, Uppy |
| **Backend** | Python 3.13, FastAPI, SQLAlchemy 2.0, Pydantic, async-first |
| **Database** | Supabase PostgreSQL + pgvector, Alembic migrations |
| **Auth** | Supabase Auth (Google OAuth + email/password) |
| **Pipeline** | AWS SQS + single Lambda (4 steps) |
| **Agent** | Claude Haiku 4.5 — manual Anthropic SDK tool loop (~50 lines) |
| **Classification** | Gemini 2.0 Flash — 8-facet ontology, visual analysis, Google Search grounding |
| **Embeddings** | OpenAI text-embedding-3-small (1536-dim, pgvector cosine search) |
| **Entity Resolution** | Google Maps, Google Books, TMDB, Spotify (direct API wrappers) |
| **Observability** | Sentry (errors), PostHog (analytics) |
| **Hosting** | Vercel (frontend), Render (API) |

### Agent & Classification

The core product is the agent layer. A manual tool loop (~50 lines, Anthropic SDK) orchestrates 6 tools that query, classify, search, analyze, and resolve content. Tools return `AgentToolResult` objects — they never raise — and all results are cached inline via upsert.

Each video is classified across 8 orthogonal facets:

| Facet | Example Labels |
|-------|---------------|
| Affect | funny, wholesome, sad, nostalgic, satisfying |
| Topic | food, fashion, comedy, technology, pets |
| Genre | tutorial, vlog, skit, recipe, asmr, meme |
| Communicative Intent | entertain, inform, persuade, sell, document |
| Creator Role | professional, amateur, brand, influencer |
| Viewer Orientation | passive_consumption, active_learning, shopping_research |
| Presentation Style | talking_head, voiceover, text_overlay, cinematic |
| Content Provenance | original, repost, duet, stitch, remix |

Each facet has a validated **tier-1** vocabulary (drives collections and aggregation) and open **tier-2** micro-labels from Gemini (drives discovery).

### Pipeline

4-step async pipeline, SQS + single Lambda, runs once per upload:

1. **Parse Export** — extract URLs from ZIP, create `media_event` rows
2. **Apify Enrich** — fetch TikTok metadata (batched, 50/call)
3. **Subtitle Fetch** — get subtitles from Apify data
4. **Embedding** — fuse text + generate 1536-dim vectors (batched, 100/call)

Every step is idempotent — safe under retries via upserts and deterministic IDs.

## Development

### Tests

```bash
# Backend (26 test files)
cd src/backend && ../../.venv/bin/pytest tests/ -v --tb=short

# Frontend
cd src/frontend && npm run typecheck && npm run lint && npm run build
```

### Lint

```bash
cd src/backend && ../../.venv/bin/ruff check . && ../../.venv/bin/ruff format .
```

### Workbench

The [workbench/](workbench/) is an AI development lab for experimenting with classification, evaluation, and data quality — no infrastructure needed.

```bash
# Batch classification with structured output
.venv/bin/python workbench/tools/classify_batch.py workbench/data/sample-videos.json --limit 5

# Run evals against golden set (per-facet accuracy)
.venv/bin/python workbench/tools/run_evals.py --verbose --save

# Generate synthetic test data via Claude
.venv/bin/python workbench/tools/generate_test_data.py "cooking videos with emoji captions" --count 10
```

## Project Structure

```
src/
  backend/
    app/
      routers/        — chat (SSE), uploads, user
      services/       — agent, tools, gemini, ontology, prompts, pipeline,
                        entity resolvers, uploads, parser, storage
      models/         — media_event, conversation, user, upload, enums
      core/           — auth, config
    alembic/          — database migrations
    tests/            — unit + integration tests
  frontend/
    src/app/          — pages: landing, login, auth, upload, chat, settings
    src/components/   — app-header, dev-banner, providers
    src/lib/          — auth-context, sse, design-tokens, supabase clients
  lambdas/
    pipeline/         — SQS handler → pipeline.py
workbench/
  tools/              — classify_batch, run_evals, generate_test_data, seed_db
  experiments/        — apify profiling, vision analysis, pipeline v3, golden set
  notebooks/          — 6 Jupyter notebooks for interactive exploration
scripts/              — dev-setup, dev-start, setup-env, check-env, seed-db
docs/                 — architecture decisions, research sprint, setup guides
```

## Documentation

| Document | Description |
|----------|-------------|
| [CLAUDE.md](CLAUDE.md) | Development reference — architecture, conventions, commands |
| [Architecture Decisions](docs/CEO_PLAN_REVIEW_2026-03-14.md) | Hybrid agentic architecture rationale |
| [Brand & Design System](docs/plans/claude-code-v0-design-files/BRAND.md) | Parchment + Ink visual identity |
| [Research Sprint](docs/research-plan-v0/) | Sprint log, unit economics, prompt audit |
| [Setup Guides](docs/setup/) | Local dev, AWS, Supabase, environment, production |

## Links

- Repository: https://github.com/s0shaheen/attic
- Issue tracker: https://github.com/s0shaheen/attic/issues
- Project board: https://github.com/users/s0shaheen/projects/2

## License

This is a private project. All rights reserved.
