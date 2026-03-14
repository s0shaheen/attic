# Changelog

All notable changes to this project will be documented in this file.

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
