# Attic MVP Development Guide

This document outlines the epic and task breakdown for the Attic MVP, derived from the [Product Requirements Document](../docs/Attic_MVP_PRD_v1.0.1.md).

---

## Overview

Attic is a personal analytics platform for TikTok data. The MVP enables users to upload their TikTok data export, enrich videos with metadata and AI analysis, and search/filter their content library.

---

## Epic Breakdown

| Epic | Name | Description |
|------|------|-------------|
| 0 | Infrastructure & Foundation | Project scaffolding, database, CI/CD, dev environment |
| 1 | Authentication | Google/Apple OAuth, JWT sessions, account management |
| 2 | Upload & Consent | ZIP upload, export parsing, scope selection |
| 3 | Processing Pipeline | 10-step async enrichment pipeline |
| 4 | Progress & Notifications | Real-time progress tracking, email/SMS notifications |
| 5 | Library View | Gallery/list views, pagination, sorting |
| 6 | Search | Keyword, semantic, and hybrid search with filters |
| 7 | Detail View | Single video view with enriched metadata |
| 8 | User Settings & Landing | Profile, settings, landing page, subscription enforcement |

---

## Epic 0: Infrastructure & Foundation

Sets up the foundational architecture for both backend and frontend.

| Task | Name | Description |
|------|------|-------------|
| 0.1 | Backend project scaffolding | FastAPI, SQLAlchemy, pytest, ruff configuration |
| 0.2 | Frontend project scaffolding | Next.js 15, TypeScript, Tailwind, shadcn/ui setup |
| 0.3 | Database setup | PostgreSQL + pgvector, initial Alembic migrations |
| 0.4 | CI/CD pipeline | GitHub Actions for lint, test, build |
| 0.5 | Local development environment | Docker Compose for local services |
| 0.6 | Environment configuration | Secrets management, .env structure |

**Dependencies:** None (foundational)

---

## Epic 1: Authentication (PRD F1)

Implements user authentication with social providers.

| Task | Name | Description |
|------|------|-------------|
| 1.1 | Google OAuth 2.0 integration | Backend OAuth flow with Google |
| 1.2 | Apple Sign-In integration | Backend OAuth flow with Apple |
| 1.3 | JWT session management | Access/refresh token handling |
| 1.4 | Auth frontend | Login page, callback handling, auth state |
| 1.5 | Sign out functionality | Token invalidation, session cleanup |
| 1.6 | Account deletion flow | GDPR-compliant account and data deletion |

**Dependencies:** Epic 0

---

## Epic 2: Upload & Consent (PRD F2 + F3)

Handles file upload and user consent for data processing.

| Task | Name | Description |
|------|------|-------------|
| 2.1 | ZIP file upload endpoint | Max 500MB, streaming upload |
| 2.2 | TikTok export parser | Extract liked/favorited URLs from export |
| 2.3 | Upload validation & error handling | File type, size, format validation |
| 2.4 | Scope selection API | liked/favorited/both selection |
| 2.5 | Consent screen UI component | Data usage disclosure, consent capture |
| 2.6 | Upload page frontend | Drag-drop interface, guide, scope selection |

**Dependencies:** Epic 0, Epic 1

---

## Epic 3: Processing Pipeline (PRD F4)

Core async pipeline that enriches uploaded videos with metadata and AI analysis.

| Task | Name | Description |
|------|------|-------------|
| 3.1 | Job queue infrastructure | Postgres-based async job queue |
| 3.2 | Pipeline orchestrator | Modal serverless orchestration |
| 3.3 | PARSE_EXPORT step | Extract URLs from ZIP |
| 3.4 | APIFY_ENRICH step | Fetch TikTok metadata (batched, 50/call) |
| 3.5 | MEDIA_DOWNLOAD step | Download video/images to storage |
| 3.6 | SUBTITLE_FETCH step | Get subtitles if available |
| 3.7 | WHISPER_TRANSCRIBE step | Transcribe audio if no subtitles |
| 3.8 | VISION_ANALYSIS step | GPT vision tagging (batched, 5 images/call) |
| 3.9 | TEXT_FUSION step | Combine all text fields |
| 3.10 | EMBEDDING step | Generate search vectors (batched, 100/call) |
| 3.11 | DERIVED_FIELDS step | Compute engagement rate, etc. |
| 3.12 | SEARCH_INDEX step | Update full-text + vector indexes |
| 3.13 | Capability interfaces | Protocol classes for vendor abstraction |
| 3.14 | Error handling & retry logic | Exponential backoff, dead letter queue |

**Dependencies:** Epic 0, Epic 2

---

## Epic 4: Progress & Notifications (PRD F8)

Real-time progress tracking and user notifications.

| Task | Name | Description |
|------|------|-------------|
| 4.1 | Progress tracking API endpoint | GET /api/uploads/{id}/progress |
| 4.2 | Processing page frontend | Real-time progress UI with step breakdown |
| 4.3 | Email notification service | Completion notification via email |
| 4.4 | SMS notification service | Optional Twilio integration |
| 4.5 | Notification preferences API | User notification settings |

**Dependencies:** Epic 0, Epic 3

---

## Epic 5: Library View (PRD F5)

Main content library interface.

| Task | Name | Description |
|------|------|-------------|
| 5.1 | Media events list API | Pagination, sorting, basic filtering |
| 5.2 | Gallery view component | Grid thumbnail layout |
| 5.3 | List view component | Table/list layout with metadata |
| 5.4 | View toggle with persistence | Remember user's view preference |
| 5.5 | Infinite scroll / pagination | Load more on scroll |
| 5.6 | Sort controls | Date, engagement, creator sorting |

**Dependencies:** Epic 0, Epic 3

---

## Epic 6: Search (PRD F6)

Full-text and semantic search capabilities.

| Task | Name | Description |
|------|------|-------------|
| 6.1 | Keyword search API | Full-text search with ts_vector |
| 6.2 | Semantic search API | pgvector similarity search |
| 6.3 | Hybrid search | Combined keyword + semantic ranking |
| 6.4 | Filter API | Creator, mood, category, date range filters |
| 6.5 | Search UI | Search bar, filter sidebar, active filters |
| 6.6 | Search results display | Results with relevance indicators |

**Dependencies:** Epic 0, Epic 3, Epic 5

---

## Epic 7: Detail View (PRD F7)

Individual video detail page.

| Task | Name | Description |
|------|------|-------------|
| 7.1 | Single media event API endpoint | GET /api/media/{id} with full data |
| 7.2 | Detail page frontend | Video player, metadata display |
| 7.3 | Confidence indicators component | AI confidence scores display |
| 7.4 | Entities display component | Tags, categories, extracted entities |
| 7.5 | Link to original TikTok | External link to source video |

**Dependencies:** Epic 0, Epic 3, Epic 5

---

## Epic 8: User Settings & Landing

User management and marketing pages.

| Task | Name | Description |
|------|------|-------------|
| 8.1 | User profile API | GET /api/user/me with usage stats |
| 8.2 | Settings page frontend | Profile, preferences, account management |
| 8.3 | Landing page | Hero, how it works, pricing sections |
| 8.4 | Subscription tier enforcement | Free tier limits, upgrade prompts |
| 8.5 | Rate limiting middleware | API rate limiting by tier |

**Dependencies:** Epic 0, Epic 1

---

## Suggested Implementation Order

### Phase 1: Foundation
1. Epic 0: Infrastructure & Foundation

### Phase 2: Core User Journey
2. Epic 1: Authentication
3. Epic 2: Upload & Consent
4. Epic 3: Processing Pipeline

### Phase 3: User Interface
5. Epic 4: Progress & Notifications
6. Epic 5: Library View
7. Epic 7: Detail View

### Phase 4: Discovery
8. Epic 6: Search

### Phase 5: Polish
9. Epic 8: User Settings & Landing

---

## Folder Structure

Each epic has a dedicated folder for task specifications:

```
tasks/
├── MVP_GUIDE.md          # This file
├── 0-infrastructure/     # Epic 0 task specs
├── 1-auth/               # Epic 1 task specs
├── 2-upload/             # Epic 2 task specs
├── 3-pipeline/           # Epic 3 task specs
├── 4-progress/           # Epic 4 task specs
├── 5-library/            # Epic 5 task specs
├── 6-search/             # Epic 6 task specs
├── 7-detail/             # Epic 7 task specs
└── 8-settings/           # Epic 8 task specs
```

---

## Task Specification Template

When creating individual task specs, use this template:

```markdown
# Task X.Y: Task Name

## Overview
Brief description of the task.

## Requirements
- [ ] Requirement 1
- [ ] Requirement 2

## Technical Details
Implementation notes, API contracts, data models.

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Dependencies
- Task X.Z (if applicable)

## Estimated Complexity
Low / Medium / High
```

---

## References

- [Product Requirements Document](../docs/Attic_MVP_PRD_v1.0.1.md)
- [CLAUDE.md](../CLAUDE.md) - Development conventions and commands
