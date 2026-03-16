# Changelog

All notable changes to this project will be documented in this file.

## [0.2.11.0] - 2026-03-16

### Changed
- Migrate task tracking from markdown files (TODO.md, TODOS.md) to GitHub Projects + Issues (#58-#103)
- Rewrite CLAUDE.md with mandatory issue tracking rules, sync points table, and deduplication instructions
- Strip CURRENT_PLAN.md to static architecture reference (remove progress tracking, handoff notes)
- Branch naming convention: `s0shaheen/issue-N-short-desc` (was `feature/{wave}-{step}-short-name`)

### Added
- GitHub Issue template (`.github/ISSUE_TEMPLATE/task.md`) with What/Why/Files Touched/Open Questions/Not In Scope
- GitHub Action (`pr-issue-check.yml`) that warns on PRs missing `Closes #N`
- Label taxonomy: 4 dimensions (priority, readiness, autonomy, component)
- Board columns: Backlog → Up Next → In Progress → Paused → Done

### Removed
- `TODO.md` — 42 items migrated to GitHub Issues
- `TODOS.md` — 8 items migrated to GitHub Issues

## [0.2.10.0] - 2026-03-16

### Added
- Email/password authentication (Supabase Auth) alongside Google OAuth — works in dev and production
- AuthProvider context (`lib/auth-context.tsx`) with `useAuth()` hook and `onAuthStateChange` listener
- PostHog frontend SDK integration with `trackAuthEvent()` helper for auth funnel analytics
- Shared AppHeader component with Radix DropdownMenu for user menu (nav, settings, sign out)
- Settings page (`/settings`) with account info, sign out, and account deletion (typed "DELETE" confirmation)
- Password reset flow: forgot password → email → `/auth/reset-password` → set new password
- Email verification screen (`/auth/verify`) for production sign-ups
- DevBanner component — shows "Dev mode" + user email in development environment
- Dev quick login: login page auto-fills test credentials when `NEXT_PUBLIC_ENVIRONMENT=development`
- Login rate limit detection: shows "Too many attempts" message on Supabase 429
- Open redirect prevention: `?next=` parameter sanitized to relative paths only (middleware + callback)
- PII sanitization: Supabase error messages stripped of email addresses before sending to PostHog
- Auth guard on settings page: redirects to /login when session expires
- Welcome message on first chat visit with suggested starter questions
- 9 new Vitest tests: AuthProvider context, AppHeader, DevBanner, `?next=` sanitization
- `seed_local.py`: creates test user via Supabase Admin API (not raw SQL into auth.users)
- `seed_local.py`: environment safety check — refuses to run against non-localhost databases
- TODO 7: Supabase email template customization (deferred)

### Changed
- Login page rebuilt: sign-in/sign-up/forgot toggle, Google OAuth + email/password, `?next=` awareness
- Chat page refactored to use AppHeader + AuthProvider (removed inline auth check)
- Upload page refactored to use AppHeader + AuthProvider
- Middleware now protects `/chat`, `/upload`, and `/settings` (was `/chat` only)
- Middleware passes `?next=` param through login redirect flow
- Auth callback sanitizes `?next=` param (open redirect prevention)
- `seed_local.py` requires `SUPABASE_SECRET_KEY` env var (no hardcoded keys)
- CLAUDE.md: Auth stack updated to include Email/Password

### Removed
- Dead `SYSTEM_PROMPT` constant from `agent.py` (35 lines, replaced by `build_system_prompt()` in prompts.py)

## [0.2.9.2] - 2026-03-16

### Changed
- Updated Claude Code settings to allow gstack directory read/write access for faster browser automation workflows

## [0.2.9.1] - 2026-03-16

### Changed
- Updated CLAUDE.md with versioning strategy: VERSION bumped only at ship time, feature branches add entries under [Unreleased], /ship promotes entries into versioned section

## [Unreleased]

## [0.2.9.0] - 2026-03-16

### Added
- `creator_details` stat type for `get_stats` tool — top 20 creators with item counts, date ranges, and top cached topics (2-query bulk fetch)
- `field_distribution` stat type for `get_stats` tool — GROUP BY + COUNT for allowlisted fields (music_name, creator_username, media_type, interaction_type)
- `field` parameter on `get_stats` tool schema (enum-constrained, required for field_distribution)
- Allowlist validation (`_AGGREGATE_FIELDS` frozenset) for field_distribution to prevent SQL injection
- Intent-mapping hints in system prompt for new stat types
- 16 new tests: creator_details (6), field_distribution (7), schema validation (3)
- TODO 7: composite index (user_id, creator_username) for aggregation query performance

## [0.2.8.2] - 2026-03-16

### Removed
- Claude Code CI Fixer workflow (auto-fix CI failures via Claude)
- Claude Code Remote Executor workflow (remote execution via GitHub Actions)

## [0.2.8.1] - 2026-03-16

### Fixed
- Chat page redirects unauthenticated users to `/login` on mount instead of showing inline error after interaction
- Ruff E501 line-too-long in auth.py issuer validation

## [0.2.8.0] - 2026-03-16

### Added
- `scripts/dev-setup.sh` — one-command local dev environment setup (creates .env files, installs deps, runs migrations, seeds test data)
- `scripts/seed_local.py` — seeds local Supabase with 10 media_events (7 restaurant, 3 other) with real OpenAI embeddings for testing

### Fixed
- pgvector cosine distance query uses `CAST(:query_vec AS vector)` instead of `::vector` cast syntax that breaks with asyncpg parameter binding
- Auth issuer validation accepts both `localhost` and `127.0.0.1` variants for local Supabase

### Changed
- `db/session.py` reads database URL from pydantic Settings instead of `os.getenv` — eliminates need for `load_dotenv` hack or `set -a; source .env`
- `build_database_url()` retained only for alembic CLI usage, documented as such

## [0.2.7.0] - 2026-03-16

### Added
- `VisionFocus` StrEnum with 6 targeted vision analysis modes: general, books, scenes, places, text, products
- Focus-specific prompt templates in `_VISION_PROMPTS` dict — each mode optimizes extraction for its content type
- `focus` parameter on `analyze_visual` tool schema (optional, enum-constrained, defaults to general)
- Explicit `VisionFocus` validation with descriptive error messages in `agent_tools.py`
- Vision focus mode guidance in system prompt (recall check + cost awareness sections)
- 13 new tests: focus prompt selection, backward compat regression, invalid focus handling, dispatcher forwarding, schema validation
- TODO 6: vision result caching with focus-aware key (deferred to post-5.5)

### Changed
- `gemini.py:analyze_visual()` accepts `focus: VisionFocus` kwarg (default GENERAL preserves backward compat)
- `agent.py` dispatcher forwards `focus` parameter from tool input to `analyze_visual`
- System prompt mentions focus modes in entity retrieval plan and cost awareness sections

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
