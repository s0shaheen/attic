# CLAUDE.md

## What is Attic?

Personal analytics platform for TikTok data. Users upload their TikTok data export ZIP, and Attic enriches each video with metadata, visual analysis, and semantic tagging.

## Stack

| Layer             | Technologies                                                 |
| ----------------- | ------------------------------------------------------------ |
| **Auth**          | Supabase Auth (Google OAuth)                                 |
| **Database**      | Supabase PostgreSQL + pgvector, SQLAlchemy 2.0, Alembic      |
| **Backend**       | Python 3.12, FastAPI                                         |
| **Frontend**      | Next.js 14, TypeScript, Tailwind, shadcn/ui, TanStack Query, React Hook Form |
| **File Upload**   | Uppy + Supabase Storage                                      |
| **Workflow**      | AWS Step Functions, AWS Lambda, AWS SQS                      |
| **AI/Enrichment** | Apify (TikTok metadata), OpenAI (vision, transcription, embeddings) |
| **Real-time**     | Supabase Realtime                                            |
| **Notifications** | Resend (email)                                               |
| **Payments**      | Stripe Billing                                               |
| **Observability** | Sentry (errors), PostHog (analytics)                         |
| **Hosting**       | Vercel (frontend), Render (API)                              |

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
npm run lint                        # Lint
npm run typecheck                   # Type check
npm run build                       # Production build

# Local Development
supabase start                      # Start local Supabase
sam local invoke FunctionName       # Test Lambda locally
```

## Architecture

### Processing Pipeline

10-step async pipeline orchestrated by AWS Step Functions:

1. `PARSE_EXPORT` → Extract URLs from ZIP, create `media_event` rows
2. `APIFY_ENRICH` → Fetch TikTok metadata (batched, 50/call)
3. `MEDIA_DOWNLOAD` → Download video/images to S3 temp
4. `SUBTITLE_FETCH` → Get subtitles if available
5. `WHISPER_TRANSCRIBE` → Transcribe via OpenAI if no subtitles
6. `VISION_ANALYSIS` → GPT-4 Vision tagging (batched, 5 images/call)
7. `TEXT_FUSION` → Combine caption + hashtags + transcript + OCR + visual_tags
8. `EMBEDDING` → Generate 1536-dim vectors (batched, 100/call)
9. `DERIVED_FIELDS` → Compute engagement_rate, interaction_hour, etc.
10. `SEARCH_INDEX` → Update full-text (GIN) + vector (ivfflat) indexes

**CRITICAL**: Every Lambda function MUST be idempotent. Use upserts and deterministic IDs.

### Capability Abstraction

Each processing step uses Protocol interfaces for vendor abstraction:

```python
# src/backend/capabilities/interfaces.py
class VideoMetadataProvider(Protocol):
    def fetch_metadata(self, urls: list[str]) -> list[VideoMetadataResult]: ...

class VisionAnalyzer(Protocol):
    def analyze(self, images: list[bytes], context: VideoContext) -> VisionAnalysisResult: ...

class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...
```

## Key Files

- `docs/MVP/PRD/Attic_MVP_PRD_v1.3.0.md` — Product spec, data model, API contracts
- `docs/MVP/tasks/Attic_MVP_Dev_Guide_v1.3.0.md` — Epic/task breakdown with status tracking
- `docs/MVP/tasks/specs/` — Individual task specifications
- `docs/MVP/tasks/SPEC_TEMPLATE.md` — Exhaustive template for task specs (12 sections)

## Development Workflow

### Task Lifecycle

1. **SPEC**: Generate spec from Dev Guide task using `/generate-specs`
2. **VALIDATE**: Check spec against PRD/production requirements using `/validate-specs`
3. **IMPLEMENT**: Build feature with tests using `/implement-backlog`
4. **VERIFY**: Run task-specific tests using `/run-task-tests`

### Spec File Convention

Each task has ONE spec file at `docs/MVP/tasks/specs/{epic}-{task_id}.md` containing:

- Implementation requirements
- Context references (which files to read)
- Test requirements
- Progress tracking (completed/remaining/blocked)
- Implementation notes

### Status Tracking

Task status is tracked in TWO places:

1. **Spec file**: Detailed progress, notes, blockers
2. **Dev Guide**: Overall status per task (NOT_STARTED | IN_PROGRESS | BLOCKED | DONE)

## Code Conventions

### Python (Backend)

- Type hints required on all functions
- Async for all I/O operations
- Pydantic models for all request/response schemas
- Repository pattern for data access
- Dependency injection via FastAPI's `Depends()`

### TypeScript (Frontend)

- Strict mode enabled
- Zod for runtime validation
- Server components by default
- TanStack Query for data fetching
- React Hook Form for forms

### Database

- All schema changes via Alembic migrations
- Never raw SQL in application code
- RLS policies on all user-owned tables
- Use SQLAlchemy ORM exclusively

### Git

- Branch: `feature/{epic}-{task}-short-name` or `fix/{task}-description`
- Commits: `feat(scope): description` (conventional commits)
- PR per task, squash merge

## Testing Requirements

### Unit Tests

- Every public function must have tests
- Mock external services (Apify, OpenAI, Stripe)
- Test edge cases and error paths

### Integration Tests

- Test API endpoints with test database
- Test Supabase RLS policies
- Test Step Functions state transitions

### Test Naming

```python
# Python: test_{function_name}_{scenario}_{expected_result}
def test_parse_export_valid_zip_returns_urls():
    ...
```

## Security Checklist (Apply to Every Task)

- [ ] Server-side auth: Validate Supabase JWT, derive user_id from token
- [ ] RLS policies verified for any new/modified tables
- [ ] No PII in logs (no tokens, emails, raw URLs)
- [ ] Input validation on all endpoints
- [ ] Rate limiting on public endpoints

## Production Readiness (from PRD §9)

Every implementation must satisfy:

1. **Idempotency**: Safe under retries (upserts, deterministic IDs)
2. **Observability**: Correlation IDs, structured logging, cost tracking
3. **Error handling**: Graceful degradation, user-visible error states
4. **Cost controls**: Per-step budget tracking, tier enforcement