# Changelog

All notable changes to this project will be documented in this file.

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
