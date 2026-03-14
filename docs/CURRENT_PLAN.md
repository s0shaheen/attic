# Attic — Current Implementation Plan

**Architecture:** Hybrid Agentic (minimal pre-processing + agent chat layer)
**Status:** Wave 3 — COMPLETE
**Last Updated:** 2026-03-14
**Full Review:** `.claude/plans/velvety-orbiting-widget.md`

---

## Quick Reference

```
LLM Stack:
  Claude Haiku 4.5     — orchestrator (tool calling, prompt-cached ontology)
  Gemini 3 Flash       — classification + vision + Google Search grounding
  OpenAI embed-3-small — embeddings for semantic search
  Direct API wrappers  — entity resolution (Maps, Books, TMDB, Spotify)

Pipeline: SQS → single Lambda (parse → apify → subtitle → embed)
Agent:    FastAPI SSE streaming, manual Anthropic SDK tool loop
Frontend: Minimal chat UI (rebuild from scratch)
```

---

## Task Checklist

### Wave 1: Cleanup + Foundation
> Dependencies: None. Do this first.

- [x] **1.1** Delete dead Lambda stubs (11 handler dirs)
- [x] **1.2** Delete old task specs (docs/MVP/tasks/specs/3-*.md — 15 files)
- [x] **1.3** Delete old frontend (src/frontend/ — kept package.json for dep reference)
- [x] **1.4** Delete dead test files (test_lambda_stubs.py — whisper/s3 tests didn't exist)
- [x] **1.5** Update CLAUDE.md — replaced with new architecture, handoff protocol, agent layer docs
- [x] **1.6** Alembic migration 006 — conversations, messages tables + cached_classifications/entities columns + GIN indexes + RLS

### Wave 2: Agent Backend
> Dependencies: Wave 1 complete (migration 006 must exist)

- [x] **2.1** `app/services/ontology.py` — ONTOLOGY_V1 dict, validate_classification(), format_ontology_for_prompt()
- [x] **2.2** `app/services/gemini.py` — Gemini 3 Flash client (classify + analyze_visual)
- [x] **2.3** `app/services/entity_resolvers.py` — Google Maps, Books, TMDB, Spotify wrappers
- [x] **2.4** `app/services/agent_tools.py` — query_items, classify, analyze_visual, resolve_entity
- [x] **2.5** `app/services/agent.py` — agent loop (~50 lines), SSE event generation
- [x] **2.6** `app/routers/chat.py` — POST /api/chat endpoint, SSE streaming, rate limiting
- [x] **2.7** `app/config.py` — add ANTHROPIC_API_KEY, GEMINI_API_KEY, entity API keys
- [x] **2.8** `app/main.py` — register chat router
- [x] **2.9** Per-user cost tracking — tool call counter (50/query, 200/hour) — built into agent.py

### Wave 3: Pipeline
> Dependencies: Wave 1 complete. Independent of Wave 2.

- [x] **3.1** `src/lambdas/pipeline/handler.py` — unified 4-step handler (parse→apify→subtitle→embed)
- [x] **3.2** Simplify `infra/template.yaml` — delete state machine + 10 Lambdas, keep SQS + 1 Lambda
- [x] **3.3** Update CommonLayer to bundle src/backend/app/

### Wave 4: Minimal Frontend + Tests
> Dependencies: Wave 2 + Wave 3 complete.

- [ ] **4.1** Scaffold fresh Next.js 14 app
- [ ] **4.2** Auth pages (login, callback) — reuse Supabase patterns
- [ ] **4.3** Chat page — message list + input + SSE streaming
- [ ] **4.4** `tests/test_ontology.py` — validation tests
- [ ] **4.5** `tests/test_agent_tools.py` — unit tests (mocked externals)
- [ ] **4.6** `tests/test_agent.py` — agent loop tests
- [ ] **4.7** `tests/test_chat_endpoint.py` — integration tests
- [ ] **4.8** `tests/test_pipeline_handler.py` — integration test
- [ ] **4.9** `tests/test_pipeline_steps.py` — unit tests per step
- [ ] **4.10** Cover critical failure gaps: entity rate limit, DB constraint, stale conversation

---

## Architecture Decisions (Quick Ref)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent hosting | Inline SSE streaming | Simple, no new infra, partial responses useful |
| Agent SDK | Manual Anthropic SDK tool loop | Full control, explicit, ~50 lines |
| Multi-model | Direct Gemini 3 Flash API in tool funcs | One model for classify + vision + grounding |
| Entity resolution | Async Python functions (not MCP) | Direct API calls, wrap in MCP later if needed |
| Chat history | DB tables (conversations + messages) | Queryable, persistent, matches existing patterns |
| Cache write-back | Inline during tool execution | Upserts before returning, survives stream drops |
| Pipeline orchestration | SQS + single Lambda | Replaces Step Functions, simple for 4 linear steps |
| Ontology storage | Python dict in ontology.py | No YAML/DB, type-safe, testable |
| Error handling | Result objects (never raise) | Matches existing Result pattern, agent explains |
| SSE format | Minimal (token + done) | No tool-status events at MVP |
| Classification storage | JSONB + GIN index on media_events | Fast containment queries, no joins |
| Embedding timing | 4th pipeline step | Semantic search works from first chat |
| Frontend | Full rebuild | Current UI not desired |

---

## Key File Paths

### Existing (Keep)
```
src/backend/app/core/auth.py              # JWT validation
src/backend/app/services/uploads.py       # Upload service
src/backend/app/services/tiktok_parser.py # ZIP parser (634 lines)
src/backend/app/services/validation.py    # Validation service
src/backend/app/services/tiers.py         # Tier limits
src/backend/app/services/user_deletion.py # GDPR deletion
src/backend/app/services/storage.py       # Supabase storage
src/backend/app/models/*.py               # SQLAlchemy models
src/backend/app/db/session.py             # Async DB session
src/backend/app/config.py                 # Settings (will edit)
src/backend/app/main.py                   # FastAPI app (will edit)
src/lambdas/common/logger.py              # Structured logging
src/lambdas/common/idempotency.py         # Deterministic UUIDs
tests/fixtures/tiktok-exports/            # 14 test fixtures
```

### New (Create)
```
src/backend/app/routers/chat.py           # Chat endpoint
src/backend/app/services/agent.py         # Agent loop
src/backend/app/services/agent_tools.py   # Tool functions
src/backend/app/services/gemini.py        # Gemini client
src/backend/app/services/ontology.py      # Ontology dict
src/backend/app/services/entity_resolvers.py  # Entity API wrappers
src/backend/alembic/versions/006_*.py     # New migration
src/lambdas/pipeline/handler.py           # Unified pipeline
src/frontend/                             # Fresh Next.js app
```

---

## Context Handoff Notes

When a conversation runs low on context, update this file:
1. Check the boxes for completed tasks above
2. Note any in-progress work in the "Current Progress" section below
3. Note any blockers or decisions needed
4. The new session reads this file + CLAUDE.md to resume

### Current Progress
_Updated by each session before ending._

**Wave:** 3 — COMPLETE. Ready to start Wave 4 (frontend + tests).
**Current step:** Done — all 3 steps complete
**Blockers:** None
**Notes:**
- Wave 3 implemented unified pipeline:
  - `src/lambdas/pipeline/handler.py` — 4-step sync handler (parse→apify→subtitle→embed)
    - Step 1: Downloads ZIP from Supabase Storage, parses with tiktok_parser, upserts media_event rows with deterministic IDs
    - Step 2: Batches URLs (50/call) to Apify TikTok scraper, maps response to media_event columns, detects media_type
    - Step 3: Advances images/slideshows past subtitle step, marks videos as subtitled
    - Step 4: Fuses text fields (caption+hashtags+subtitles+creator+music), batches to OpenAI embeddings (100/call)
    - Uses sync SQLAlchemy (psycopg2) + stdlib urllib for HTTP — no async complexity in Lambda
    - Idempotent: deterministic IDs via generate_idempotency_key(), processing_state gating per step
    - Progress tracking via UploadPipelineRun updates after each batch
  - `infra/template.yaml` — simplified from 589→188 lines
    - Deleted: 11 Lambda functions, 11 log groups, Step Functions state machine + role + log group
    - Kept: S3 bucket, SQS queue + DLQ, IAM role (removed states:StartExecution)
    - Added: Single PipelineFunction with SQS trigger (BatchSize: 1), SAM parameters for secrets
  - `src/lambdas/Makefile` — SAM build target for CommonLayer
    - Copies common/ + ../backend/app/ into layer artifacts
    - Lambda runtime adds /opt/ to sys.path, so both packages importable
  - `src/lambdas/pipeline/requirements.txt` — sqlalchemy, psycopg2-binary, pydantic, pgvector
- All files pass ruff lint + format
