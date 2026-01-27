# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Attic?

Personal analytics platform for TikTok data. Users upload their TikTok data export ZIP, and Attic enriches each video with metadata, visual analysis, and semantic tagging to enable intelligent filtering, search, and behavioral insights.

## Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0, Supabase PostgreSQL + pgvector
- **Frontend**: Next.js 14, TypeScript, Tailwind, shadcn/ui, TanStack Query
- **Auth**: Supabase Auth (Google/Apple OAuth)
- **Processing**: Temporal.io (workflows), Modal (serverless), Apify (TikTok metadata), OpenAI (vision, transcription, embeddings)
- **Notifications**: Resend (email), Twilio (SMS)
- **Payments**: Stripe Billing

## Commands

```bash
# Backend (from src/backend/)
pytest tests/ -v                    # Run all tests
pytest tests/test_file.py -v        # Run single test file
pytest tests/test_file.py::test_fn  # Run single test
ruff check .                        # Lint
ruff format .                       # Format
alembic upgrade head                # Run migrations
alembic revision --autogenerate -m "description"  # Create migration

# Frontend (from src/frontend/)
npm test                            # Run tests
npm test -- --watch                 # Watch mode
npm run lint                        # Lint
npm run typecheck                   # Type check
npm run build                       # Production build
```

## Architecture

### Processing Pipeline

The core of Attic is a 10-step async processing pipeline that enriches uploaded videos:

1. `PARSE_EXPORT` → Extract URLs from ZIP
2. `APIFY_ENRICH` → Fetch TikTok metadata (batched, 50/call)
3. `MEDIA_DOWNLOAD` → Download video/images
4. `SUBTITLE_FETCH` → Get subtitles if available
5. `WHISPER_TRANSCRIBE` → Transcribe if no subtitles
6. `VISION_ANALYSIS` → GPT vision tagging (batched, 5 images/call)
7. `TEXT_FUSION` → Combine all text fields
8. `EMBEDDING` → Generate search vectors (batched, 100/call)
9. `DERIVED_FIELDS` → Compute engagement rate, etc.
10. `SEARCH_INDEX` → Update full-text + vector indexes

Each step uses a **capability interface** (Protocol class) to abstract vendors. See `src/backend/capabilities/interfaces.py`.

### Backend Patterns

- **Repository pattern** for data access
- **Dependency injection** via FastAPI's `Depends()`
- **Pydantic models** for validation and serialization
- **Temporal.io workflows** for async processing (replaces Postgres job queue)

### Frontend Patterns

- **Server components** by default
- **Zod** for runtime validation
- Minimal client state

### Key Database Tables

- `users` - Auth and subscription info (includes Stripe customer ID)
- `uploads` - User upload sessions (includes Temporal workflow ID)
- `upload_pipeline_runs` - Processing progress tracking
- `media_events` - Core table: enriched video data with pgvector embeddings
- `processing_steps` - Per-video, per-step processing logs

## Conventions

### Code Style
- Python: Type hints required, async for I/O, Pydantic models
- TypeScript: Strict mode, Zod validation, server components default
- Tests: Write alongside implementation (TDD approach)

### Git
- Branch: `feature/123-short-name` or `fix/456-bug-name`
- Commits: `feat(scope): description` (conventional commits)
- PRs: Reference issue number, include test coverage

### Database
- All schema changes via Alembic migrations
- Never raw SQL in app code (use SQLAlchemy)

## Current Work

Check `gh issue list --milestone "v0.1.0"` for active tasks.

## Key Files

- `docs/MVP/Attic_MVP_PRD_v1.1.0.md` — Full product spec, data model, API contracts
- `docs/MVP/ADR/Attic_MVP_Tech_Stack_Changes.md` — Tech stack decisions and rationale
- `tasks/MVP/MVP_GUIDE_v1.1.0.md` — Epic and task breakdown for MVP
- `docs/architecture.md` — System architecture (when created)
- `tasks/*.md` — Detailed specs for each task
