# Attic — Exhaustive Status Report

_Prepared: 2026-05-19. For matching against incoming PRD._

---

## 1. What Attic Is (Current Framing)

A **personal content intelligence platform**. Users upload their TikTok or Instagram data exports (ZIP files). Attic processes them through a classification + embedding pipeline, then makes the library explorable through a conversational chat interface. The core value proposition is: _turn your saved content into a searchable, organized library you can actually talk to_.

Brand: "Attic." Parchment + Ink palette. DM Sans body font. Crimson Pro for display (currently unused in product UI). Dark-mode skewed implementation (neutral-950 throughout — design tokens defined but not yet applied).

---

## 2. Current Capabilities (What Is Actually Working)

### 2.1 Data Ingestion Pipeline

**Both TikTok and Instagram are supported.**

| Step                         | What It Does                                                                                                                                                      | Status                                                            |
| ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| ZIP Upload                   | User uploads export ZIP via presigned S3 URL. Uppy handles the browser side.                                                                                      | ✅ Working                                                        |
| parse_export                 | Extracts items from TikTok (`favorites.json`) or Instagram (`saved_posts_1.json`, `saved_collections.json`). Zip-slip defense. DM/story filtering. Privacy-aware. | ✅ Working                                                        |
| apify_enrich                 | Enriches TikTok URLs via Apify. Full metadata: video_url, thumbnail, audio, captions, creator stats.                                                              | ✅ Working (expensive: $0.014/item)                               |
| TikWM primary                | TikWM as cheaper primary enrichment, Apify as fallback. Validated: 100% success on 50 URLs.                                                                       | ✅ Working ($0.001/item, 14x cheaper than Apify — merged PR #125) |
| subtitle_fetch               | Fetches captions/subtitles. 77% coverage on golden set (82/106 items).                                                                                            | ✅ Working                                                        |
| perceive (Tier 1)            | Keyframe visual analysis via Gemini Flash. Fast, cheap (~$0.0009/item). Runs at upload time.                                                                      | ✅ Working                                                        |
| perceive (Tier 2)            | Full video analysis via Gemini File API. More comprehensive (~$0.003/item). Background.                                                                           | ✅ Implemented; trigger/queue design undecided                    |
| classify                     | 8-facet ontology classification via Gemini Flash. 111 Tier-1 labels. Open micro-labels for Tier 2.                                                                | ✅ Working                                                        |
| embed                        | OpenAI text-embedding-3-small (1536-dim). Stored in pgvector. Cosine similarity search.                                                                           | ✅ Working                                                        |
| Instagram collections import | Imports user's Instagram collections as Attic collections with source badges.                                                                                     | ✅ Working                                                        |

**Unit economics (Tier 1 + Tier 2 + embeddings):** ~$0.0194/item total ingestion cost.

**Dev mode:** Zero API keys needed. Fake providers for Apify, Gemini, OpenAI. Inline BackgroundTasks instead of SQS. Fully functional locally.

### 2.2 Classification System (8-Facet Ontology)

Defined in `app/services/ontology.py`. Eight orthogonal dimensions:

1. **Affect/mood** — emotional tone (calm, energetic, playful, melancholic, etc.)
2. **Topic/subject** — what the content is about (food, travel, fitness, fashion, etc.)
3. **Genre** — content format (tutorial, review, vlog, comedy, aesthetic, etc.)
4. **Intent** — why the creator made it (educate, entertain, inspire, sell, etc.)
5. **Creator role** — creator's relationship to content (expert, documenter, performer, etc.)
6. **Viewer orientation** — how the viewer relates (learn, be entertained, get inspired, etc.)
7. **Presentation style** — visual/production style (raw, polished, lo-fi, cinematic, etc.)
8. **Provenance** — platform context (TikTok, Instagram, creator tier, etc.)

**111 Tier-1 labels total** across the 8 facets. These drive aggregation and structured queries. Tier-2 is open Gemini micro-labels that drive semantic discovery.

### 2.3 Agent Chat

Manual Anthropic SDK tool loop (~50 lines, no framework). Claude Haiku 4.5 orchestrator.

**6 agent tools:**

| Tool             | Purpose                                                                      |
| ---------------- | ---------------------------------------------------------------------------- |
| `query_items`    | Structured DB queries with JSONB classification filters, pagination, sorting |
| `classify`       | On-demand reclassification of items (Gemini Flash)                           |
| `analyze_visual` | Visual analysis with Google Search grounding (Gemini Flash)                  |
| `search_similar` | pgvector cosine similarity search (1536-dim OpenAI embeddings)               |
| `get_stats`      | Aggregate queries: counts, distributions, top-N                              |
| `resolve_entity` | External entity resolution: Google Maps, Google Books, TMDB, Spotify         |

**SSE streaming protocol:** 5 event types over a single HTTP connection:

- `meta` — sets conversation_id
- `token` — streams text tokens
- `media_grid` — renders horizontal scroll card grid with thumbnails
- `entity_card` — renders entity with type badge + metadata key-value pairs
- `stat_card` — renders stat summary with formatted numbers
- `tool_activity` — parsed but not rendered in UI yet (deferred)
- `error` / `done` — control flow

**Cost controls:** 50 tool calls/query max, 200 tool calls/hour/user.

**Conversation history:** conversation_id tracked per session. Multi-turn context maintained.

### 2.4 Collections

Three creation modes:

- **Manual:** User-created, named
- **Agent-driven:** Future (1I — UX undecided, blocked)
- **Import:** Instagram saved collections imported with source badges

Schema: `collections` + `collection_items` tables. Denormalized counts. JSONB metadata. RLS enforced.

**Auto-collection (entity grouping) was attempted and DEFERRED** — false positives in entity grouping made it unreliable. Remains a post-alpha item.

### 2.5 Auth

Supabase Auth. Two sign-in methods:

- Google OAuth (custom SVG button, `/auth/callback` PKCE flow)
- Email/password with password reset flow

Server-side JWT validation. `get_current_user` dependency returns `AuthenticatedUser(id, email)`. RLS policies enforced at DB layer (50+ integration tests covering cross-user isolation, FK attacks, anonymous access).

### 2.6 Frontend (What's Rendered Today)

**9 pages, all implemented:**

| Page                   | Status     | Notes                                                                    |
| ---------------------- | ---------- | ------------------------------------------------------------------------ |
| `/`                    | ✅ Working | Auth check → routes to `/chat` or `/login`                               |
| `/login`               | ✅ Working | Multi-mode: sign-in, sign-up, reset. Google OAuth. Dev-mode prefill.     |
| `/upload`              | ✅ Working | 3-step Uppy flow. Progress bar. Success/error states.                    |
| `/chat`                | ✅ Working | SSE streaming, markdown rendering, media grids, entity cards, stat cards |
| `/settings`            | ✅ Working | Email, sign-out, account deletion with confirmation                      |
| `/auth/verify`         | ✅ Working | Email verification confirmation page                                     |
| `/auth/reset-password` | ✅ Working | Password reset form with validation                                      |
| `/auth/callback`       | ✅ Working | OAuth exchange, open-redirect defense                                    |

**No browse/search/explore pages exist.** Discovery is exclusively through the chat interface.

**Design system gap:** Design tokens defined in `lib/design-tokens.ts` and CSS custom properties in `globals.css` (parchment/ink/cinnamon), but UI is implemented with hardcoded Tailwind classes (`bg-neutral-950`, `bg-blue-600`, `text-neutral-300`). Dark mode throughout — Parchment palette not applied to product UI.

### 2.7 Deployment (Current Infra)

| Layer              | Provider                             | Status                                                  |
| ------------------ | ------------------------------------ | ------------------------------------------------------- |
| Frontend           | Vercel                               | ✅ Auto-deploy from main                                |
| Backend API        | Render (starter: 0.5 CPU, 512MB RAM) | ✅ Working, but too small for production                |
| Database           | Supabase PostgreSQL + pgvector       | ✅ Working. 11 migrations applied.                      |
| Pipeline           | AWS SQS + Lambda                     | ✅ Configured, deployed via SAM                         |
| Storage            | S3 (presigned URLs)                  | ✅ Working                                              |
| Email              | Resend                               | ✅ Working (pipeline completion email — merged PR #129) |
| Analytics          | PostHog                              | ✅ Tracking key events                                  |
| Error tracking     | Sentry                               | ⚠️ In-progress (task 3A)                                |
| Structured logging | —                                    | ❌ Not done (task 3B)                                   |

---

## 3. Experimentation / Research Completed

**7 workbench experiments** conducted and documented:

| Experiment                 | What Was Tested                                         | Key Finding                                                                                                            |
| -------------------------- | ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| 01 — Apify Profiling       | Apify cost and performance characteristics              | $0.014/item, ~2min/50 items                                                                                            |
| 02 — Vision Analysis       | Gemini Flash visual analysis capabilities               | Validated Gemini File API for video; Google Search grounding for richer context                                        |
| 03 — Pipeline V3           | Two-tier pipeline (Tier 1 keyframe + Tier 2 full video) | Total ~$0.0194/item. Configurable concurrency (20 workers/step). 360s time budget.                                     |
| 04 — Golden Set            | 106 real TikTok items for evaluation                    | 82/106 with subtitles. Stratified sample. Used as eval ground truth.                                                   |
| 05 — Agent Evaluation      | 12-query test suite against golden set                  | Categories: simple filter, overview, vibe/semantic, entity retrieval, multi-step. Results saved with per-query timing. |
| 06a — Media Type Benchmark | Performance by content type (video/slideshow/image)     | Informs media-type-specific perception prompts                                                                         |
| 06b — TikWM Benchmark      | TikWM vs Apify on 50 real URLs                          | 100% success, 14x cheaper ($0.001 vs $0.014), 5x faster. 21/28 fields match Apify.                                     |
| 07 — Gemma4 Benchmark      | Gemma 4 31B vs Gemini Flash on 55 items, all 8 facets   | 68.3% overall agreement (best: provenance 81%, worst: creator_role 50%). Gemini Flash stays as prod classifier.        |

**Workbench tools (production-quality):**

- `classify_batch.py` — batch classification with structured output, timing, error handling
- `run_evals.py` — per-facet accuracy benchmarking against hand-labeled golden set (exit code 0 if ≥60% accuracy)
- `seed_db.py`, `seed_from_apify.py` — DB seeding for eval
- `backfill_v2.py` — re-process existing items with v2 prompts (dry-run supported)

---

## 4. Known Limitations

### Technical

- **No content browse/explore UI** — discovery is chat-only. No grid, filter, sort, or search page.
- **Render starter plan** — 0.5 CPU, 512MB RAM. Will fail under concurrent user load. Must upgrade before invites.
- **TikWM free quota** — 1,000 items/month. Exhausted quickly at scale. Paid tier pricing unknown.
- **Slideshow TikToks** — No test data. Behavior unverified with real slideshow URLs.
- **Auto-collections DEFERRED** — entity grouping had too many false positives. Needs fundamentally different approach (likely LLM-driven per-item).
- **tool_activity SSE events** — parsed in frontend, not rendered. Deferred.
- **Tier 2 pipeline trigger** — queue design and mixed Tier1/Tier2 agent handling not finalized (task 1D+).
- **Design system not applied** — parchment/ink tokens defined but UI uses hardcoded Tailwind classes.
- **No mobile responsiveness** — not yet addressed (task 2H).
- **No pagination UI** — long chat histories or large content sets have no load-more.

### Product/UX

- **Entire Layer 2 (frontend)** — 10 tasks, all pending. This is the critical alpha blocker.
- **No processing status page** — users see a spinner after upload, no progress indication or art slideshow.
- **No library/content browser** — users can't browse their imported content except through chat.
- **No conversation history** — past conversations not surfaced in a sidebar (task 2G).
- **No feedback mechanism** — no thumbs up/down on agent responses (task 2J).
- **No empty states** — 16 empty state variants needed, none implemented (task 2I).
- **No post-processing email follow-up** — completion email is sent, but no re-engagement email sequence exists.

---

## 5. Open / Undecided Things

| Question                        | Why It Matters                                                           | Status                               |
| ------------------------------- | ------------------------------------------------------------------------ | ------------------------------------ |
| TikWM paid plan tier            | Free quota (1000/month) insufficient for production                      | Needs pricing check at tikwmapi.com  |
| Tier 2 queue design             | Separate SQS queue or reuse? Impacts upload UX and cost tracking         | Undecided (1D+)                      |
| Collection-from-chat UX         | How do users save agent results as collections?                          | Blocked on product UX decisions (1I) |
| Brand scope for Layer 2         | Complete parchment/ink reskin vs MVP subset?                             | Undecided (gates 2A onward)          |
| Render upgrade timing           | Before first invites or post-alpha?                                      | Undecided                            |
| Email opt-in on processing page | Do we collect email during processing wait?                              | Undecided (2D)                       |
| IG folder upload                | Instagram exports are folders, not ZIPs — needs UX consideration (2E-ig) | Undecided                            |
| Spotify integration (1F)        | Playlist creation from music-related content                             | Deferred post-alpha                  |

---

## 6. Overall Completion Status (Alpha Tracker Layers)

| Layer                     | What                                                                                                 | Done                        | Pending        | Gate?                 |
| ------------------------- | ---------------------------------------------------------------------------------------------------- | --------------------------- | -------------- | --------------------- |
| **0 — Foundations**       | Agent prompts, prompt versioning, collections DB, RLS                                                | **4/4 (100%)**              | —              | ✅ GATE PASSED        |
| **1 — Backend**           | Platform parsers, pipeline v2, enrichment, notifications, rate limits                                | **6/10 (60%)** — 2 deferred | 1D+, 1I        | ⚠️ Gate items pending |
| **2 — Frontend**          | Brand, chat rebuild, library, processing page, walkthroughs, history, mobile, empty states, feedback | **0/10 (0%)**               | ALL            | ❌ CRITICAL BLOCKER   |
| **3 — Hardening**         | Sentry, logging, admin, privacy, fallbacks, upload limits, cost controls, cascade                    | **3/8 (38%)** (3E, 3F, 3H)  | 3A, 3B, 3D, 3G | ⚠️ Gate items pending |
| **4 — Deploy & Validate** | Prod deploy, founder test, second account, tester docs, invites, observe                             | **0/6 (0%)**                | ALL            | ❌ Depends on L2+L3   |

---

## 7. Remaining Steps to Alpha Readiness

**Status as of 2026-05-19:** Backend is substantially complete. Layer 2 (all frontend) is the blocker. A PRD with new UX, brand name, and product direction is incoming — Layer 2 scope should not be locked until the PRD is reviewed.

### Immediate (pre-PRD)

- Finalize TikWM paid plan pricing (free quota 1000/month insufficient)
- Make Tier 2 queue design decision (1D+) — separate SQS queue or reuse?
- Decide on collection-from-chat scope (1I) — in-scope or post-alpha?
- Upgrade Render from starter plan before first user invites

### After PRD review

- Lock Layer 2 scope against PRD requirements (name change, UX paradigm, platform scope)
- Layer 2: Brand (2A → gates all others), chat rebuild (2B), library endpoints + UI (2C), processing page (2D), platform walkthroughs (2E), conversation history (2G), mobile (2H), empty states (2I), feedback (2J)
- Layer 3 remaining: Sentry (3A), structured logging (3B), privacy callout (3D), cost controls (3G)

### Ship

- 4-DEPLOY: Prod runbook + Render upgrade
- 4A: Process founder's full TikTok export end-to-end in production
- 4B: Process second test account
- 4C-4F: Tester onboarding → invite first 5 → observe → invite remaining ~15

---

## 8. What Will Need Updating When PRD Arrives

This report documents the _current reality_. When the PRD arrives, the following areas are most likely to need reconciliation:

1. **App/brand name change** — all UI copy, login page, email templates, Vercel project name, Render service name, Supabase project name
2. **UX paradigm** — if PRD moves away from chat-as-primary-discovery, significant Layer 2 rework
3. **Content type scope** — if PRD adds new platforms (YouTube, Twitter/X, Pinterest), parser work required
4. **Ontology/classification changes** — if PRD changes what facets matter, re-classify golden set + backfill existing items
5. **Collections model** — if PRD has a specific UX for collections (auto-generation, sharing, etc.)
6. **Processing UX** — how users experience the pipeline wait (task 2D)
7. **Monetization model** — if PRD introduces tiers, the `tiers.py` service exists but billing system (Stripe) pending

---

## 9. Key File Locations

| Area                                            | Path                                                                |
| ----------------------------------------------- | ------------------------------------------------------------------- |
| Alpha tracker (source of truth for task status) | `docs/ALPHA_TRACKER.md`                                             |
| Brand spec                                      | `docs/BRAND.md`                                                     |
| Classification ontology                         | `src/backend/app/services/ontology.py`                              |
| Agent tool loop                                 | `src/backend/app/services/agent.py`                                 |
| Agent tools                                     | `src/backend/app/services/agent_tools.py`                           |
| Pipeline                                        | `src/backend/app/services/pipeline.py`                              |
| DB models                                       | `src/backend/app/models/`                                           |
| Alembic migrations                              | `src/backend/alembic/versions/`                                     |
| Chat page (frontend)                            | `src/frontend/src/app/chat/page.tsx`                                |
| SSE parsing                                     | `src/frontend/src/lib/sse.ts`                                       |
| Design tokens                                   | `src/frontend/src/lib/design-tokens.ts`                             |
| Experiments                                     | `workbench/experiments/` (01–07)                                    |
| Eval tools                                      | `workbench/tools/run_evals.py`, `workbench/tools/classify_batch.py` |
| Golden set                                      | `workbench/data/golden_set_template.json`                           |
