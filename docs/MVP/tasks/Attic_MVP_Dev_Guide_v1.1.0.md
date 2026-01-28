# Attic MVP Development Guide

This document outlines the epic and task breakdown for the Attic MVP, derived from the [Product Requirements Document](../../docs/MVP/Attic_MVP_PRD_v1.1.0.md).

**Version:** 1.1.0
**Last Updated:** 2026-01-24

---

## Overview

Attic is a personal analytics platform for TikTok data. The MVP enables users to upload their TikTok data export, enrich videos with metadata and AI analysis, and search/filter their content library.

### Tech Stack (v1.1.0)

See [ADR: Tech Stack Changes](../../docs/MVP/ADR/Attic_MVP_Tech_Stack_Changes.md) for detailed rationale.

| Layer | Technologies |
|-------|--------------|
| **Auth** | Supabase Auth (Google/Apple OAuth) |
| **Database** | Supabase PostgreSQL + pgvector |
| **Backend** | FastAPI + SQLAlchemy 2.0 + FastAPI-Users + FastAPI-Pagination |
| **Frontend** | Next.js 14 + shadcn/ui + TanStack Query + React Hook Form |
| **File Upload** | Uppy + Supabase Storage |
| **Job Queue** | Temporal.io |
| **Processing** | Modal (serverless) |
| **Real-time** | Supabase Realtime |
| **Notifications** | Resend (email) + Twilio (SMS) |
| **Payments** | Stripe Billing |
| **Observability** | Sentry + Axiom + Highlight.io + PostHog |
| **Security** | Cloudflare + Upstash |
| **Hosting** | Vercel + Render + Modal |

---

## Epic Breakdown

| Epic | Name | Description |
|------|------|-------------|
| 0 | Infrastructure & Foundation | Project scaffolding, database, CI/CD, dev environment |
| 1 | Authentication | Supabase Auth integration, session management |
| 2 | Upload & Consent | Uppy upload, Supabase Storage, export parsing, consent |
| 3 | Processing Pipeline | Temporal.io workflows, 10-step enrichment pipeline |
| 4 | Progress & Notifications | Supabase Realtime, Resend email, Twilio SMS |
| 5 | Library View | Gallery/list views, pagination, sorting |
| 6 | Search | Keyword, semantic, and hybrid search with filters |
| 7 | Detail View | Single video view with enriched metadata |
| 8 | User Settings & Landing | Profile, settings, landing page, Stripe Billing |

---

## Epic 0: Infrastructure & Foundation

Sets up the foundational architecture for both backend and frontend.

| Task | Name | Description |
|------|------|-------------|
| 0.1 | Backend project scaffolding | FastAPI, SQLAlchemy 2.0, FastAPI-Users, FastAPI-Pagination, pytest, ruff |
| 0.2 | Frontend project scaffolding | Next.js 14 (App Router), TypeScript, Tailwind, shadcn/ui setup |
| 0.3 | Supabase project setup | Create Supabase project, enable pgvector, configure RLS policies |
| 0.4 | Database migrations | SQLAlchemy + Alembic setup, initial schema migrations |
| 0.5 | Temporal.io setup | Local Temporal server, Python SDK, workflow definitions |
| 0.6 | CI/CD pipeline | GitHub Actions for lint, test, build |
| 0.7 | Local development environment | Docker Compose for Temporal, local Supabase CLI |
| 0.8 | Environment configuration | Secrets management, .env structure, Supabase keys |

**Dependencies:** None (foundational)

---

## Epic 1: Authentication (PRD F1)

Implements user authentication via Supabase Auth with social providers.

| Task | Name | Description |
|------|------|-------------|
| 1.1 | Supabase Auth Google OAuth | Configure Google OAuth provider in Supabase |
| 1.2 | Supabase Auth Apple Sign-In | Configure Apple Sign-In provider in Supabase |
| 1.3 | Supabase session management | Next.js auth helpers, JWT handling, token refresh |
| 1.4 | Backend auth middleware | FastAPI middleware to validate Supabase JWTs |
| 1.5 | Auth frontend | Login page with Google/Apple buttons, callback handling |
| 1.6 | Sign out functionality | Session cleanup, token invalidation |
| 1.7 | Account deletion flow | GDPR-compliant account and data deletion |

**Dependencies:** Epic 0

---

## Epic 2: Upload & Consent (PRD F2 + F3)

Handles file upload via Uppy and Supabase Storage, plus user consent.

| Task | Name | Description |
|------|------|-------------|
| 2.1 | Supabase Storage bucket setup | Create upload bucket, configure RLS, set size limits |
| 2.2 | Presigned URL API | Backend endpoint to generate Supabase Storage presigned URLs |
| 2.3 | Uppy integration | Configure Uppy with Supabase Storage, progress tracking |
| 2.4 | TikTok export parser | Extract liked/favorited URLs from export ZIP |
| 2.5 | Upload validation & error handling | File type, size, format validation |
| 2.6 | Scope selection API | liked/favorited/both selection |
| 2.7 | Consent screen UI component | Data usage disclosure, consent capture |
| 2.8 | Upload page frontend | Uppy drag-drop, guide, scope selection, consent modal |

**Dependencies:** Epic 0, Epic 1

---

## Epic 3: Processing Pipeline (PRD F4)

Core async pipeline using Temporal.io for workflow orchestration.

| Task | Name | Description |
|------|------|-------------|
| 3.1 | Temporal.io workflow definition | VideoProcessingWorkflow with all activities |
| 3.2 | Temporal activity: PARSE_EXPORT | Extract URLs from ZIP |
| 3.3 | Temporal activity: APIFY_ENRICH | Fetch TikTok metadata (batched, 50/call) |
| 3.4 | Temporal activity: MEDIA_DOWNLOAD | Download video/images to temp storage |
| 3.5 | Temporal activity: SUBTITLE_FETCH | Get subtitles if available |
| 3.6 | Temporal activity: WHISPER_TRANSCRIBE | Transcribe audio if no subtitles |
| 3.7 | Temporal activity: VISION_ANALYSIS | GPT vision tagging (batched, 5 images/call) |
| 3.8 | Temporal activity: TEXT_FUSION | Combine all text fields |
| 3.9 | Temporal activity: EMBEDDING | Generate search vectors (batched, 100/call) |
| 3.10 | Temporal activity: DERIVED_FIELDS | Compute engagement rate, etc. |
| 3.11 | Temporal activity: SEARCH_INDEX | Update full-text + vector indexes |
| 3.12 | Modal integration | Serverless execution of compute-heavy activities |
| 3.13 | Capability interfaces | Protocol classes for vendor abstraction |
| 3.14 | Error handling & retry policies | Temporal retry policies, dead letter handling |
| 3.15 | Progress update signals | Temporal signals to update pipeline_run status |

**Dependencies:** Epic 0, Epic 2

---

## Epic 4: Progress & Notifications (PRD F8)

Real-time progress tracking and user notifications.

| Task | Name | Description |
|------|------|-------------|
| 4.1 | Progress tracking API endpoint | GET /api/uploads/{id}/status |
| 4.2 | Supabase Realtime integration | Subscribe to upload_pipeline_runs changes |
| 4.3 | Processing page frontend | Real-time progress UI via Supabase Realtime |
| 4.4 | Resend email integration | Completion notification emails |
| 4.5 | Twilio SMS integration | Optional SMS notifications |
| 4.6 | Notification preferences API | User notification settings CRUD |

**Dependencies:** Epic 0, Epic 3

---

## Epic 5: Library View (PRD F5)

Main content library interface.

| Task | Name | Description |
|------|------|-------------|
| 5.1 | Media events list API | FastAPI-Pagination, sorting, basic filtering |
| 5.2 | TanStack Query data layer | Query hooks for media events |
| 5.3 | Gallery view component | Grid thumbnail layout with shadcn/ui Card |
| 5.4 | List view component | Table layout with metadata |
| 5.5 | View toggle with persistence | LocalStorage preference |
| 5.6 | Infinite scroll | TanStack Query infinite queries |
| 5.7 | Sort controls | Date, engagement, creator sorting |

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
| 6.5 | Search UI | Search bar, filter sidebar with shadcn/ui components |
| 6.6 | Search results display | Results with relevance indicators |

**Dependencies:** Epic 0, Epic 3, Epic 5

---

## Epic 7: Detail View (PRD F7)

Individual video detail page.

| Task | Name | Description |
|------|------|-------------|
| 7.1 | Single media event API endpoint | GET /api/media-events/{id} with full data |
| 7.2 | Detail page frontend | Metadata display with shadcn/ui |
| 7.3 | Confidence indicators component | AI confidence scores display |
| 7.4 | Entities display component | Tags, categories, extracted entities |
| 7.5 | Link to original TikTok | External link to source video |

**Dependencies:** Epic 0, Epic 3, Epic 5

---

## Epic 8: User Settings & Landing

User management, payments, and marketing pages.

| Task | Name | Description |
|------|------|-------------|
| 8.1 | User profile API | GET /api/user/me with usage stats |
| 8.2 | Settings page frontend | Profile, preferences with React Hook Form |
| 8.3 | Stripe Billing integration | Products, subscriptions, webhook handling |
| 8.4 | Stripe Customer Portal | Link to Stripe-hosted billing management |
| 8.5 | Landing page | Hero, how it works, pricing sections |
| 8.6 | Subscription tier enforcement | Free tier limits, upgrade prompts |
| 8.7 | Upstash rate limiting | API rate limiting by tier |
| 8.8 | Cloudflare setup | CDN, DDoS protection, page rules |

**Dependencies:** Epic 0, Epic 1

---

## Observability Tasks (Cross-cutting)

These tasks should be integrated early and maintained throughout.

| Task | Name | Description |
|------|------|-------------|
| O.1 | Sentry integration | Error tracking for backend + frontend |
| O.2 | Axiom logging | Structured logging for backend |
| O.3 | Highlight.io setup | Session replay + APM |
| O.4 | PostHog analytics | Event tracking, user identification |

**Dependencies:** Epic 0

---

## Suggested Implementation Order

### Phase 1: Foundation
1. Epic 0: Infrastructure & Foundation (0.1-0.8)
2. Observability Tasks (O.1-O.4)

### Phase 2: Core User Journey
3. Epic 1: Authentication
4. Epic 2: Upload & Consent
5. Epic 3: Processing Pipeline

### Phase 3: User Interface
6. Epic 4: Progress & Notifications
7. Epic 5: Library View
8. Epic 7: Detail View

### Phase 4: Discovery
9. Epic 6: Search

### Phase 5: Polish & Monetization
10. Epic 8: User Settings & Landing

---

## Folder Structure

Each epic has a dedicated folder for task specifications:

```
tasks/
├── MVP/
│   ├── MVP_GUIDE_v1.1.0.md    # This file
│   ├── 0-infrastructure/      # Epic 0 task specs
│   ├── 1-auth/                # Epic 1 task specs
│   ├── 2-upload/              # Epic 2 task specs
│   ├── 3-pipeline/            # Epic 3 task specs
│   ├── 4-progress/            # Epic 4 task specs
│   ├── 5-library/             # Epic 5 task specs
│   ├── 6-search/              # Epic 6 task specs
│   ├── 7-detail/              # Epic 7 task specs
│   ├── 8-settings/            # Epic 8 task specs
│   └── observability/         # Observability task specs
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

### Tools/Libraries
- Library 1: Purpose
- Library 2: Purpose

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Dependencies
- Task X.Z (if applicable)

## Estimated Complexity
Low / Medium / High
```

---

## Key Technology Decisions (v1.1.0)

| Decision | Rationale |
|----------|-----------|
| **Supabase Auth over custom OAuth** | Drop-in OAuth, JWT management, RLS integration |
| **Temporal.io over Postgres queue** | Multi-step workflow orchestration, automatic retries, visual debugging |
| **Supabase Realtime over polling** | Zero setup, built-in reconnection, RLS-aware |
| **Uppy over custom upload** | Resumable uploads, progress tracking, direct-to-storage |
| **shadcn/ui over custom components** | Copy-paste ownership, Radix accessibility, Tailwind styling |
| **TanStack Query over fetch/SWR** | Caching, pagination helpers, optimistic updates |
| **Stripe Billing over custom payments** | Industry standard, customer portal, dunning handling |

---

## References

- [Product Requirements Document v1.1.0](../../docs/MVP/Attic_MVP_PRD_v1.1.0.md)
- [ADR: Tech Stack Changes](../../docs/MVP/ADR/Attic_MVP_Tech_Stack_Changes.md)
- [CLAUDE.md](../../CLAUDE.md) - Development conventions and commands

---

## Changelog

### v1.1.0 (2026-01-24)
- Updated all epics to reflect tech stack changes from ADR
- Epic 0: Added Supabase project setup (0.3), Temporal.io setup (0.5), updated Docker Compose for Temporal
- Epic 1: Replaced custom OAuth with Supabase Auth tasks
- Epic 2: Added Supabase Storage, Uppy integration tasks
- Epic 3: Replaced Postgres queue with Temporal.io workflow tasks
- Epic 4: Added Supabase Realtime, Resend, Twilio tasks
- Epic 5: Added TanStack Query data layer tasks
- Epic 8: Added Stripe Billing, Upstash rate limiting, Cloudflare tasks
- Added Observability Tasks section (Sentry, Axiom, Highlight.io, PostHog)
- Added Key Technology Decisions section

### v1.0.0 (2026-01-18)
- Initial MVP development guide
