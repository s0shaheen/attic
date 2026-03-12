# Lessons Learned

Architecture retrospective from building Attic — a personal analytics platform for TikTok data.

## What Went Well

### Documentation-first development

Writing the PRD, dev guide, and 37 task specs before code forced clarity on scope and dependencies. Every task had acceptance criteria, context references, and test requirements before implementation began. This made the first three epics (23 tasks) ship cleanly with minimal rework.

### Security as a day-one concern

Treating security as foundational rather than a polish step paid off:

- **TikTok parser** (634 lines) included zip-slip defense, path traversal prevention, symlink detection, and 10MB extraction limits from the first commit
- **Auth system** validated JWTs against both HS256 and ES256, with structured error codes and JWKS integration
- **RLS policies** were written alongside every migration, not bolted on later
- **Data minimization** — the parser only reads whitelisted files (Like List, Favorites), ignoring DMs, search history, and watch history even though they're in the export

### Managed services over custom infrastructure

Choosing Supabase (auth + database + storage + realtime) and AWS serverless (Step Functions + Lambda) eliminated weeks of infrastructure work. The tradeoff — vendor lock-in — was acceptable for an MVP. The ADR process helped document these decisions and their alternatives (Clerk, Auth0, custom JWT, etc.).

### Synthetic test fixtures

Building tools to generate synthetic TikTok exports (~13K lines each) and slice them into edge cases (empty exports, missing fields, null values) was more valuable than collecting real test data. The fixtures were deterministic, shareable, and covered format variations that real data might not surface.

## What I'd Do Differently

### Start with the parser, not the platform

The TikTok parser was the most reusable and interesting piece of the project. Building it inside a full-stack app meant it was coupled to SQLAlchemy models, Pydantic schemas, and FastAPI dependencies. Extracting it later for [portable-ai-data-kit](https://github.com/s0shaheen/portable-ai-data-kit) required untangling those dependencies. Starting with a standalone CLI tool and adding the platform layer on top would have been faster.

### Validate AI API costs early

The 10-step pipeline (Apify metadata, media download, Whisper transcription, GPT-4 Vision, embeddings) was designed on paper but never costed against real data. A quick prototype processing 10 real videos through the full pipeline would have surfaced the per-item cost and helped decide whether the economics worked before building the orchestration infrastructure.

### Scope the MVP to one enrichment type

The pipeline tried to do everything — metadata, transcription, vision analysis, text fusion, embeddings, derived fields, search indexing. An MVP that just parsed exports and showed a clean timeline (no AI enrichment) would have delivered user value in a fraction of the time, with AI features added incrementally.

### Keep Lambda count low

Designing 10 separate Lambda functions (plus error handler) created a large surface area of stubs, test files, IAM roles, and deployment config. Consolidating into 3-4 Lambdas with internal step routing would have reduced the infrastructure overhead while keeping the logical separation.

## Architecture Decisions Worth Revisiting

| Decision | Rationale | In Hindsight |
|----------|-----------|--------------|
| Step Functions for orchestration | Visual workflow, built-in retries, per-step error handling | Good choice — but 10 steps was too many for an MVP |
| pgvector for embeddings | Keeps vectors in PostgreSQL, no separate vector DB | Right call — Supabase supports it natively, avoids Pinecone/Weaviate dependency |
| Capability Protocol interfaces | Vendor abstraction for Apify, OpenAI, etc. | Over-engineered for a solo project — direct SDK calls would have been fine |
| Alembic migrations | Schema versioning, rollback support | Essential — 5 migrations tracked real schema evolution |
| Uppy for uploads | Resumable uploads, drag-and-drop, progress tracking | Good DX but heavy for a ZIP-only upload flow |

## Key Numbers

- **23/78 tasks completed** (Epics 0-2: Infrastructure, Auth, Upload)
- **634 lines** in the TikTok parser (the most valuable artifact)
- **70+ fields** per media event in the schema
- **5 migrations** tracking schema evolution
- **60+ tests** across backend and frontend
- **37 task specs** written before implementation
- **10 Lambda stubs** that never got implemented (the signal to archive)

## The Takeaway

The most useful output of a project isn't always the project itself. Attic's parser, security patterns, and test fixture approach all survived into the successor project. The platform infrastructure — auth, upload flow, Step Functions orchestration — was well-built but solved a problem that didn't need that much machinery. Build the smallest thing that proves the idea, then add infrastructure.
