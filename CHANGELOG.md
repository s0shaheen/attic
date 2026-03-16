# Changelog

All notable changes to this project will be documented in this file.

## [0.2.6.0] - 2026-03-16

### Added
- System prompt module (`prompts.py`) with `build_system_prompt()` — cached, testable, DRY
- 5 explicit query plan templates: entity retrieval, creator aggregation, simple filter, interpretive/vibe, ambiguous/broad
- Full ontology integration in system prompt via `format_ontology_for_prompt()`
- Recall check instruction: analyze_visual on low-text items after entity searches
- Cost awareness rules: prefer cheap tools first, limit vision calls
- Disambiguation rules: default to most specific intent, fallback to semantic search
- 10 new unit tests for prompt content, caching, and DRY compliance
- TODO 5: prompt regression eval suite (deferred to post-5.1)

### Removed
- Inline `SYSTEM_PROMPT` constant from `agent.py` (35 lines replaced by `prompts.py` import)

## [0.2.5.0] - 2026-03-16

### Changed
- Restructured `TODO.md` from flat parking lot into prioritized execution tracker with Phase 1-3 roadmap
- TODO items now use canonical format: What/Why/Context/Effort/Priority/Depends-on
- Organized by phase: Phase 1 (Ship MVP, P0/P1), Phase 2 (Discovery + Conditional, P2/P3), Phase 3 (Moat, P4), Deferred Product
- 3 P0 items (system prompt rewrite, targeted vision, RLS hardening), 7 P1 items, 9 P2, 6 P3, 17 P4
- Merged overlapping items: entity rate limit + conversation 404 → Error Handling Polish
- Added `CURRENT_PLAN.md` pointer to Wave 5 as next phase

### Added
- CEO plan review decisions documented: credit system storage (user_credits table), credit reset (lazy), aggregate_field injection protection (allowlist), prompt storage (prompts.py module), credit check performance (single read/write), credit feature flag (CREDITS_ENABLED)

## [0.2.4.0] - 2026-03-16

### Added
- `search_similar` agent tool — pgvector cosine similarity semantic search with OpenAI embeddings
- `get_stats` agent tool — 5 stat types: overview, top_creators, top_hashtags, interaction_timeline, classification_breakdown
- `POST /api/uploads/process` endpoint — simplified SQS pipeline trigger for founder testing (202 async)
- Upload page (`/upload`) — Uppy drag-drop file upload with presigned URL flow and pipeline trigger
- Conversation starter prompt chips on empty chat state
- Markdown rendering for assistant messages (react-markdown + remark-gfm + @tailwindcss/typography)
- `sqs_queue_url` config setting for pipeline processing
- `TODOS.md` with 4 deferred work items (video cards, pipeline feedback, HNSW index, frontend tests)
- 14 new backend tests: 4 search_similar, 6 get_stats, 4 process endpoint

### Changed
- System prompt expanded with all 6 tools, intent-reading guidelines, markdown formatting, follow-up suggestions
- Classification breakdown uses single `jsonb_each()` query instead of per-facet f-string SQL

## [0.2.3.0] - 2026-03-15

### Removed
- ~40 dead test stub files (old 10-step Lambda pipeline + Step Functions tests)
- ~35 stale documentation files (`docs/MVP/` tree, `REPO_STATUS.md`, handoff doc)
- Dead models: `PromptTemplate`, `ProcessingStep` (tables remain in DB via migrations)
- Empty directories: `.conductor/`, `infra/staging/`, `requirements/`, `app/repositories/`
- Tracked build artifacts from git (`src/lambdas/tests/six*`, `.pyc` files, `.entire/`)
- Duplicate `eslint.config.js` (kept `.mjs`), unused Jest devDependencies
- `stepfunctions` from docker-compose LocalStack SERVICES

### Added
- `/ready` endpoint with DB connectivity check (liveness vs readiness separation)
- Tool registry decorator (`@tool`) — co-locates Anthropic schema with tool functions
- SSE parsing utility (`lib/sse.ts`) extracted from chat page with 8 unit tests
- `vitest.config.ts` with path alias support for frontend tests
- Spotify token cache TTL (expires 100s before actual token expiry)
- Conversation history rolling window (last 30 messages)
- `.gitignore` entries for `.aws-sam/`, `.ruff_cache/`, `.entire/`, `tsconfig.tsbuildinfo`

### Changed
- CORS now reads from `CORS_ORIGINS` env var via Settings (was hardcoded to localhost)
- httpx clients reused at module level in `gemini.py` and `entity_resolvers.py`
- Anthropic client reused at module level in `agent.py` (reads key from Settings lazily)
- `app/services/__init__.py` no longer eagerly imports all services (fixes Lambda import hack)
- Lambda handler removed `sys.modules` stub workaround for `app.services`
- Chat page uses extracted `parseSSEChunk()` utility instead of inline parsing
- `CEO_PLAN_REVIEW` doc marked as superseded with deprecation note

### Fixed
- `_get_anthropic_client()` no longer accepts stale API key parameter

## [0.2.2.0] - 2026-03-15

### Added
- Fresh Next.js 16 frontend: App Router, Tailwind v4, dark theme, TypeScript strict mode
- Login page with Google OAuth via Supabase Auth (`@supabase/ssr`)
- Chat page with SSE streaming, message bubbles, auto-scroll, error handling
- Auth middleware protecting `/chat` routes with session refresh
- 401 retry with automatic token refresh in chat client
- 202 backend unit tests across 9 test files (136 new):
  - `test_agent_tools.py` — 40 tests for DB-backed tool functions
  - `test_chat_endpoint.py` — 15 tests for SSE streaming endpoint
  - `test_critical_failures.py` — 14 tests for rate limits, DB constraints, graceful degradation
  - `test_pipeline_handler.py` — 21 tests for Lambda handler orchestration
  - `test_pipeline_steps.py` — 46 tests for pipeline pure functions and helpers
- Pipeline handler cherry-picked from unmerged Wave 3 branch
- Supabase publishable/secret key naming convention across all env files

### Changed
- Entity resolution API keys (Maps, TMDB, Spotify) now optional — agent tools degrade gracefully
- Stripe, Resend API keys now optional for MVP development
- Renamed `SUPABASE_SERVICE_KEY` → `SUPABASE_SECRET_KEY` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` → `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` across all config, env files, and docker-compose

### Fixed
- JSON.parse in SSE parser wrapped in try/catch to handle malformed chunks
- Middleware error handling for unreachable Supabase (treats as unauthenticated)
- Removed stale root `package-lock.json` that caused Next.js Turbopack to use wrong workspace root, preventing middleware from loading

## [0.2.1.1] - 2026-03-14

### Fixed
- Migration 006: changed `cached_classifications`/`cached_entities` columns from JSON to JSONB with `jsonb_ops` operator class for GIN index compatibility
- Pipeline handler: URL normalization (`tiktokv.com` → `tiktok.com`) for Apify TikTok scraper compatibility
- Pipeline handler: stub `app.services` package to avoid eager import of backend config in Lambda context

### Added
- `scripts/sam-build.sh` wrapper for SAM container builds (copies backend `app/` into layer mount)

## [0.2.1.0] - 2026-03-14

### Added
- Unified 4-step pipeline Lambda handler: parse_export → apify_enrich → subtitle_fetch → embed
- Idempotent processing with deterministic IDs and processing_state gating per step
- Apify TikTok scraper integration with batched URL processing (50/call) and poll-for-completion
- OpenAI embedding generation with text fusion and batched API calls (100/call)
- Media type detection (video/image/slideshow) from Apify response
- SAM Makefile-based CommonLayer build bundling backend app/ for Lambda reuse

### Changed
- Simplified SAM template from 589 to 188 lines: replaced Step Functions + 11 Lambdas with single SQS-triggered Lambda
- Removed StepFunctionsRole, 11 CloudWatch log groups, and state machine definition
- Added SAM parameters for database and API credentials (DATABASE_URL, SUPABASE_URL/KEY, APIFY, OPENAI)

## [0.2.0.0] - 2026-03-14

### Added
- Agent orchestrator: Claude Haiku 4.5 loop with manual Anthropic SDK tool calling, SSE streaming, per-query and per-hour rate limits
- 4 agent tools: `query_items`, `classify`, `analyze_visual`, `resolve_entity`
- Two-tier ontology (8 facets) with validated tier-1 labels and free-form tier-2 micro-labels
- Chat endpoint (POST `/api/chat`) with SSE streaming and conversation persistence
- Entity resolvers: Google Maps Places, Google Books, TMDB, Spotify API wrappers
- Gemini 3 Flash client for classification and visual analysis with Google Search grounding
- DB migration for `conversations`, `messages` tables with GIN indexes and RLS policies
- `cached_classifications` and `cached_entities` JSONB columns on media_events
- 66 unit tests for ontology, entity resolvers, Gemini client, and agent loop

### Fixed
- Agent loop break condition that skipped tool_use blocks when `stop_reason == "end_turn"`

## [0.1.0.0] - 2026-03-01

### Added
- TikTok data export parser (ZIP extraction, URL parsing, media_event creation)
- Supabase Auth integration (Google OAuth, JWT validation)
- User management with GDPR-compliant account deletion
- File upload pipeline (Uppy + Supabase Storage, presigned URLs)
- 4-step processing pipeline (parse, enrich, subtitle, embed) via SQS + Lambda
- Apify integration for TikTok metadata enrichment
- OpenAI embeddings (1536-dim vectors via pgvector)
- SQLAlchemy 2.0 models with Alembic migrations
- Comprehensive test suite (231 tests)
- CI/CD workflows (GitHub Actions)
