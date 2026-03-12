# Attic — Repository Status

*Last updated: 2026-03-11*

Attic is a personal analytics platform for TikTok data. Users upload their TikTok data export ZIP, and Attic enriches each media item with metadata, visual analysis, and semantic tagging.

---

## Epic Status Overview

| Epic | Name | Tasks | Status |
|------|------|-------|--------|
| 0 | Infrastructure & Foundation | 9/9 done | **COMPLETE** |
| 1 | Authentication | 6/6 done | **COMPLETE** |
| 2 | Upload & Consent | 8/8 done | **COMPLETE** |
| 3 | Processing Pipeline | 0/15 done | NOT STARTED |
| 4 | Progress & Notifications | 0/5 done | NOT STARTED (blocked by Epic 3) |
| 5 | Library View | 0/7 done | NOT STARTED (blocked by Epic 3) |
| 6 | Search | 0/6 done | NOT STARTED (blocked by Epic 3) |
| 7 | Detail View | 0/5 done | NOT STARTED (blocked by Epic 3) |
| 8 | User Settings & Landing | 0/7 done | NOT STARTED |
| 9 | Production Readiness | 0/10 done | NOT STARTED |

**23 of ~78 total tasks completed (Epics 0-2). Epic 3 is the next major milestone.**

---

## What's Implemented

### Backend (src/backend/)

**FastAPI Application — Functional**
- `app/main.py`: FastAPI app running with CORS, health check endpoint, router registration
- `app/core/auth.py`: Full JWT validation (HS256 + ES256), Supabase JWKS integration, structured error codes
- `app/core/config.py`: Pydantic Settings with environment validation

**Database Schema — Fully Defined**
- 5 Alembic migrations applied (`001` through `005`):
  - `001_initial_schema`: users, uploads, upload_pipeline_runs, media_events, processing_steps, prompt_templates, cost_models + RLS policies + pgvector/pg_trgm extensions
  - `002_add_media_type`: media_type column for multi-media support
  - `003_rename_progress_fields`: media-agnostic naming (items_* instead of videos_*)
  - `004_add_validation_fields`: validation result fields on uploads
  - `005_add_consent_fields`: consent tracking fields
- ORM models fully defined:
  - `User` — auth, subscription tier, soft delete
  - `Upload` — status tracking, file_hash, Step Functions ARN
  - `MediaEvent` — 70+ fields including pgvector (1536-dim), JSONB distributions, vision/AI fields
  - `UploadPipelineRun` — progress tracking with items_* fields
  - `ProcessingStep`, `CostModel`, `PromptTemplate`

**Services — Core Logic Implemented**
- `services/tiktok_parser.py`: **Production-ready** TikTok ZIP export parser (634 lines). Security-hardened with zip-slip defense, path traversal prevention, symlink detection. Handles multiple TikTok export format variations.
- `services/validation.py`: Upload validation pipeline (ZIP integrity, export structure, video counting)
- `services/uploads.py`: Presigned URL generation, scope selection with tier limit checking. Database integration stubbed (TODO).
- `services/user_deletion.py`: GDPR-compliant deletion — storage files, Supabase Auth, confirmation email via Resend
- `services/tiers.py`: Tier definitions and processing time estimates
- `services/storage.py`: Supabase Storage presigned URL generation

**Pydantic Schemas — Complete**
- `schemas/tiktok_export.py`: TikTokVideoReference, TikTokExportSummary, TikTokParsedExport, exception hierarchy (InvalidExportError, EmptyExportError, ZipSecurityError)
- `schemas/uploads.py`: ScopeType, ValidationResult, ScopeSelectionResponse, ConsentRequest/Response

**API Routers — Endpoints Defined, Partial DB Integration**
- `POST /api/uploads/presigned-url` — functional
- `POST /api/uploads/{id}/validate` — endpoint exists, database lookup stubbed (TODO)
- `PATCH /api/uploads/{id}/scope` — endpoint exists, database lookup stubbed (TODO)
- `POST /api/uploads/{id}/consent` — endpoint exists, database lookup stubbed (TODO)
- `DELETE /api/user/me` — functional (calls UserDeletionService)

### Frontend (src/frontend/)

**Auth Flow — Implemented**
- Login page with Google sign-in (`LoginContent.tsx`, `GoogleSignInButton.tsx`)
- OAuth callback handler (`auth/callback/route.ts`)
- Sign-out route (`auth/signout/route.ts`)
- Auth error display (`AuthError.tsx`)
- Session middleware (`middleware.ts`)
- Supabase provider setup (`SupabaseProvider.tsx`)

**Upload Flow — Implemented**
- `UploadFlow.tsx`: Multi-step upload orchestration
- `TikTokUploader.tsx`: Drag-and-drop file upload with Uppy
- `SimpleFileUploader.tsx`: Fallback uploader
- `ConsentModal.tsx`: Data consent collection
- `ScopeSelector.tsx`: Liked/favorited scope selection
- `ExportGuide.tsx`: TikTok export instructions
- `UploadProgress.tsx`: Upload progress display
- `UploadSummary.tsx`: Tier usage and estimated processing time
- `UploadError.tsx`, `ValidationError.tsx`: Error handling components

**Other Pages — Scaffolded**
- `app/processing/[id]/page.tsx`: Processing status page (placeholder for Task 4.3)
- `app/settings/page.tsx`: Account settings with delete account modal
- `app/page.tsx`: Landing page
- Layout with Header and UserMenu

**Supporting Code**
- `hooks/useUploadFlow.ts`, `hooks/useUppy.ts`, `hooks/useUser.ts`
- `lib/api/uploads.ts`: API client
- `lib/supabase/`: Client, server, middleware, auth helpers
- `lib/consent/content.ts`: Consent modal copy
- `lib/errors/upload.ts`: Upload error handling
- `lib/uppy/config.ts`: Uppy file uploader configuration
- UI components: avatar, button, card, dialog, dropdown-menu, input (shadcn/ui)

### Lambda Functions (src/lambdas/)

**All 10 pipeline handlers are stubs** — they return placeholder responses and are not yet implemented:

| Step | Handler | Status |
|------|---------|--------|
| 1. PARSE_EXPORT | `parse_export/handler.py` | Stub |
| 2. APIFY_ENRICH | `apify_enrich/handler.py` | Stub |
| 3. MEDIA_DOWNLOAD | `media_download/handler.py` | Stub |
| 4. SUBTITLE_FETCH | `subtitle_fetch/handler.py` | Stub |
| 5. WHISPER_TRANSCRIBE | `whisper_transcribe/handler.py` | Stub |
| 6. VISION_ANALYSIS | `vision_analysis/handler.py` | Stub |
| 7. TEXT_FUSION | `text_fusion/handler.py` | Stub |
| 8. EMBEDDING | `embedding/handler.py` | Stub |
| 9. DERIVED_FIELDS | `derived_fields/handler.py` | Stub |
| 10. SEARCH_INDEX | `search_index/handler.py` | Stub |
| Error | `error_handler/handler.py` | Stub |

**Shared Lambda utilities implemented:**
- `common/logger.py`: Structured logging setup
- `common/idempotency.py`: Idempotency decorator pattern

### Infrastructure

**AWS (infra/)**
- `infra/template.yaml`: SAM/CloudFormation template defining S3 temp bucket (7-day lifecycle), SQS queue with DLQ, IAM roles, Step Functions state machine, all 10 Lambda functions
- `infra/samconfig.toml` + `infra/staging/samconfig.toml`: Deployment configs

**Docker**
- `docker-compose.yml`: LocalStack (S3, SQS, Step Functions, Lambda) + backend service
- `docker-compose.override.yml`: Local dev overrides
- `.docker/`: Docker build configurations

**Supabase**
- Project configured with local dev support (`supabase/`)
- Auth, Storage, Realtime channels set up

---

## Test Coverage

### Implemented Tests (Real Logic, Passing)

**Backend unit tests:**
- `test_health.py`: Health endpoint tests
- `test_auth.py`: ~17 JWT validation tests (expired tokens, invalid signatures, wrong issuer, missing claims)
- `test_tiktok_parser.py`: ~15 parser tests (multiple scopes, format variations, zip-slip, edge cases)
- `test_uploads.py`: Upload service with mocked storage
- `test_validation.py`: ZIP structure validation
- `test_scope_selection.py`: Scope selection logic
- `test_consent.py`: Consent flow
- `test_user_deletion.py`: GDPR deletion compliance
- `test_storage_bucket.py`: Storage configuration
- `test_models.py`: Model validation

**Frontend tests (10 files, Vitest + React Testing Library):**
- `TikTokUploader.test.tsx`: ~20 tests (drag-drop, file validation, size limits, states)
- `UploadError.test.tsx`, `UploadProgress.test.tsx`: Component tests
- `uploads.test.ts`: API client tests
- `config.test.ts`: Uppy configuration
- `client.test.ts`, `server.test.ts`, `middleware.test.ts`: Supabase tests
- `useUser.test.ts`: Hook tests
- `middleware.test.ts`: Request middleware

### Stub Tests (Structure Defined, Not Yet Implemented)

All Epic 3 tests are stubs with `pytest.skip()`:
- 9 Lambda handler unit test files (`unit/lambdas/test_*.py`)
- 8 capability interface test files (`unit/capabilities/test_*.py`)
- 12 integration test files (`integration/lambdas/test_*.py`, `integration/step_functions/test_*.py`)
- `unit/test_error_handling.py`, `unit/test_progress_update.py`
- `integration/test_error_handling_integration.py`, `integration/test_media_download.py`, `integration/test_progress_realtime.py`

### Test Fixtures

Located at `tests/fixtures/tiktok-exports/`:
- `real/`: Real anonymized export (gitignored)
- `synthetic/`: `user_alice.json`, `user_bob.json` (~13K lines each)
- `slices/`: minimal, watch_history_only, comments_only, likes_only, favorites_only
- `anonymized/`: `full_anonymized.json`
- `edge_cases/`: missing_fields, null_values, extra_fields, empty_export, malformed_json
- Fixture generation tools in `tests/tools/`: generate_synthetic, anonymize_export, slice_export

---

## Documentation

| Document | Location | Status |
|----------|----------|--------|
| PRD (v1.3.0) | `docs/MVP/PRD/Attic_MVP_PRD_v1.3.0.md` | Complete |
| Dev Guide (v1.3.0) | `docs/MVP/tasks/Attic_MVP_Dev_Guide_v1.3.0.md` | Complete |
| Task Specs | `docs/MVP/tasks/specs/` | 37 specs (0-0.1 through 3-3.15) |
| Spec Template | `docs/MVP/tasks/SPEC_TEMPLATE.md` | Complete (12 sections) |
| ADRs | `docs/MVP/ADR/` | Tech stack changes, production readiness |
| Setup Guides | `docs/setup/` | 7 guides (local-dev, aws, supabase, environment, staging, ci-cd, storage) |
| CLAUDE.md | Root | Project instructions for Claude Code |

---

## What's Not Built Yet

1. **Processing pipeline (Epic 3)**: All 10 Lambda handlers need implementation. This is the critical path — enrichment, transcription, vision analysis, embeddings, and search indexing.
2. **Capability providers**: Protocol interfaces exist in the PRD but no implementations (Apify, OpenAI Vision/Whisper/Embeddings, S3 downloader).
3. **Progress tracking (Epic 4)**: Real-time pipeline progress via Supabase Realtime.
4. **Library view (Epic 5)**: Browse/filter/search enriched media.
5. **Search (Epic 6)**: Full-text + vector similarity search.
6. **Detail view (Epic 7)**: Individual media event with all enrichment data.
7. **Settings & landing (Epic 8)**: Public landing page, account settings, data export.
8. **Production readiness (Epic 9)**: Cost tracking, rate limiting, observability, Stripe billing.
9. **Router DB integration**: Upload validate/scope/consent endpoints have TODOs for database queries.
