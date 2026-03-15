# Attic — Current Implementation Plan

**Architecture:** Hybrid Agentic (minimal pre-processing + agent chat layer)
**Status:** Wave 4 — COMPLETE
**Last Updated:** 2026-03-15
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

- [x] **4.1** Scaffold fresh Next.js 14 app
- [x] **4.2** Auth pages (login, callback) — reuse Supabase patterns
- [x] **4.3** Chat page — message list + input + SSE streaming
- [x] **4.4** `tests/test_ontology.py` — validation tests (existed from Wave 2)
- [x] **4.5** `tests/test_agent_tools.py` — unit tests (mocked externals)
- [x] **4.6** `tests/test_agent.py` — agent loop tests (existed from Wave 2)
- [x] **4.7** `tests/test_chat_endpoint.py` — integration tests
- [x] **4.8** `tests/test_pipeline_handler.py` — integration test
- [x] **4.9** `tests/test_pipeline_steps.py` — unit tests per step
- [x] **4.10** Cover critical failure gaps: entity rate limit, DB constraint, stale conversation

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

**Wave:** 4 — COMPLETE (all 10 tasks done)
**Current step:** Done
**Blockers:** None
**Notes:**
- Wave 4 session (2026-03-15):
  - 200 backend tests passing across 9 test files
  - Pipeline handler was on `feature/wave-2-agent-backend` (never merged to main after Wave 2 PR). Cherry-picked into working tree.
  - Frontend: Next.js app with App Router, Supabase auth (Google OAuth), SSE chat page, Tailwind v4. Build passes clean.
  - Branch: `feature/wave4-tests-frontend`
- Prior waves: Wave 1 (cleanup), Wave 2 (agent backend), Wave 3 (pipeline)
