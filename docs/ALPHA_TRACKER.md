# Attic Friends Alpha — Tracker

**Goal:** Ship the full experience to 15-20 friends.
**Gate:** All `YES` tasks complete and deployed. `NO` tasks can ship after first invites.
**Last updated:** 2026-04-02

---

`[ ]` Not started · `[~]` Planned · `[>]` In progress · `[x]` Done · `[!]` Blocked

## Layer 0: Foundations

| ID | Task | Status | Depends on | Gate? |
|----|------|--------|------------|-------|
| 0A | Agent prompt port + SSE protocol | [x] PR #119 | — | YES |
| 0B | Prompt versioning system | [x] PR #120 | — | YES |
| 0C | Collections DB migration | [x] PR #120 | — | YES |
| 0D | RLS hardening + negative tests | [x] PR #120 | — | YES |

**0A** — Ported v3 prompts from workbench into production agent. Defined 5 structured SSE event types (media_grid, entity_card, stat_card, tool_activity, error) with JSON payloads. Agent cost controls: 50 tool calls/query, 200/hour/user. Frontend chat page renders all event types inline.

**0B** — Extracted all prompts into `src/backend/prompts/` with `registry.json` manifest. 19 prompt files across 4 sets (agent/v1, classify/v1+v2, perception/v1+v2, vision/v1). `prompt_loader.py` handles loading with caching and startup validation. SHA-256 regression test confirms byte-for-byte match.

**0C** — Added `collections` and `collection_items` tables (migration 008) supporting three source modes: manual, agent (linked to conversations), and import (from Instagram exports, linked to uploads). CHECK constraint on source_type, position ordering, denormalized item_count, JSONB metadata.

**0D** — Replaced coarse `FOR ALL USING` with explicit per-operation policies (SELECT/INSERT/UPDATE/DELETE with WITH CHECK) on 6 user-owned tables. 50+ integration tests covering cross-user isolation, FK relationship attacks, anonymous access, service role bypass. Closes #60.

## Layer 1: Backend

| ID | Task | Status | Depends on | Gate? |
|----|------|--------|------------|-------|
| 1A | Auto-collection generation | [~] DEFERRED | 0A, 0C | NO |
| 1B | Instagram parser | [x] PR #121 | — | NO |
| 1C | Instagram pipeline + collection import | [x] PR #121 | 1B, 0C | NO |
| 1D | Pipeline v2: perceive + classify + video analysis | [x] PR #126 | 0A | NO |
| 1D+ | Background Tier 2 trigger at upload | [ ] | 1D | NO |
| 1E | TikWM primary enrichment | [>] Issue #123 | — | NO |
| 1F | Spotify integration | [ ] | 0A | NO |
| 1G | Email notification on processing complete | [ ] | — | YES |
| 1H | Rate limiting + error handling | [ ] | — | YES |
| 1I | Collection-from-chat agent tool | [ ] | 0C, 0A | NO |

**1A** — DEFERRED. Rule-based entity grouping was implemented and tested against 1334 real IG posts but produced too many false positives even with intent-based filtering (primary entity + actionable viewer_orientation). Needs a fundamentally different approach — likely LLM-driven per-item collection assignment rather than entity-type grouping. Demoted from gate to non-gate. Collections remain available via manual, agent, and import modes.

**1B** — Instagram data export ZIP parser. Handles saved posts (`saved_posts.json`) and user-created collections (`saved_collections.json`). Extracts /p/, /reel/, /tv/ URL patterns with shortcode extraction. Collections-only exports supported as fallback. Zip-slip defense, whitelisted paths, privacy filtering (blocks DMs/comments/stories).

**1C** — Platform dispatch in parse + enrich steps via `source_platform` parameter. Instagram Apify scraper integration with response mapping. IG collection import during parse step. Gemini model upgraded to 3-flash-preview.

**1D** — Full 2-pass pipeline: `step_perceive` (visual observation via Gemini) → `step_classify` (8-facet classification with multi-label affect, embedding_text, entities). Media-type-specific perception prompts (video, slideshow, image). Gemini File API infrastructure for full video analysis (upload, poll, delete). Configurable concurrency (PERCEIVE_CONCURRENCY=20, CLASSIFY_CONCURRENCY=20) with time budget enforcement (STEP_TIME_BUDGET_S=360s). DB columns `video_url` and `comments_top` added (migration 011).

**1D+** — After upload-time Tier 1 classification, trigger the full v2 pipeline in background. Overwrites Tier 1 data with richer perceive+classify output. Queue design and mixed Tier 1/Tier 2 agent handling still need decisions.

**1E** — TikWM API replaces Apify as primary TikTok enrichment. Experiment complete: 100% success rate on 50 real URLs, 14x cheaper ($0.001 vs $0.014/item), ~5x faster. Branch `s0shaheen/tikwm-primary-enrichment` has implementation (1 commit). Full handoff doc: `docs/TIKWM_HANDOFF.md`. Needs rebase + PR + merge.

**1F** — Spotify OAuth + playlist creation from music entities. CSV fallback for other integrations.

**1G** — Email via Resend when pipeline finishes.

**1H** — Per-user rate limits. Backoff on 429s. SSE error recovery. GitHub issues #70, #71.

**1I** — New agent tool for saving chat results as a collection. Needs product decisions about UX first.

## Layer 2: Frontend

| ID | Task | Status | Depends on | Gate? |
|----|------|--------|------------|-------|
| 2A | Apply brand kit to all screens | [ ] | — | YES |
| 2B | Chat page rebuild | [~] | 0A, 2A | YES |
| 2C | Library view + API endpoints | [ ] | 0C, 2A | YES |
| 2D | Processing page | [ ] | 1G, 2A | YES |
| 2E-tt | Upload walkthrough — TikTok | [ ] | 2A | YES |
| 2E-ig | Upload walkthrough — Instagram | [ ] | 1B | NO |
| 2F | Instagram collection display | [ ] | 1C, 2C | NO |
| 2G | Conversation history | [ ] | 2B | YES |
| 2H | Mobile responsiveness | [ ] | 2B, 2C | YES |
| 2I | Empty states | [ ] | 2B, 2C | YES |
| 2J | Feedback mechanism | [ ] | 2B | YES |

**2A** — Reskin all existing screens with Parchment + Ink. Design tokens and component specs exist in the repo.

**2B** — Functional but unbranded. Chat page (496 lines) renders all 5 SSE event types (media_grid with horizontal scroll, entity_card with tag+metadata, stat_card with tables, tool_activity, streaming tokens). Has session handling, conversation ID tracking, 401 refresh, starter prompts, markdown rendering. Needs brand pass (2A) and polish for alpha.

**2C** — New route. All-items grid + collections grid. Full-stack: backend endpoints for listing/filtering collections and items don't exist yet. Decisions about pagination, sort, and collection detail layout.

**2D** — Real progress UI replacing placeholder. Art slideshow during wait (public domain paintings). Email opt-in. Decisions about art source, slideshow behavior, progress granularity.

**2E-tt** — Improve TikTok export guide copy. Step-by-step with screenshots.

**2E-ig** — Add Instagram path. Platform selector. May need folder upload support.

**2F** — Imported IG collections appear in library with source badge.

**2G** — Past conversations in sidebar, click to load history. DB tables already exist. May need new backend endpoints.

**2H** — Sidebar collapses, cards stack, grid adapts. Mobile spec exists in design docs.

**2I** — 16 empty state variants. Copy exists in design docs.

**2J** — Thumbs up/down on responses. Full-stack: new feedback table + endpoint + UI.

## Layer 3: Hardening

| ID | Task | Status | Depends on | Gate? |
|----|------|--------|------------|-------|
| 3A | Sentry | [ ] | — | YES |
| 3B | Structured logging (no PII) | [ ] | — | NO |
| 3C | Admin aggregate view | [ ] | 3B | NO |
| 3D | Privacy callout in onboarding | [ ] | — | YES |
| 3E | Fallback handling | [ ] | 0A | YES |
| 3F | Upload size limits + time estimates | [ ] | — | YES |
| 3G | Cost controls | [ ] | 1H | YES |
| 3H | Data deletion cascade verification | [ ] | 0C | YES |

**3E** — Graceful degradation when external APIs are down. Each pipeline step and agent tool needs a failure path.

**3G** — Agent-level cost controls already exist (0A: 50 tool calls/query, 200/hour/user). Remaining work is per-user credits/billing system (issue #72) and upstream rate limit enforcement.

**3H** — Verify delete account cascades through all tables including collections. Test with full user data.

## Layer 4: Deploy & Validate

| ID | Task | Status | Depends on | Gate? |
|----|------|--------|------------|-------|
| 4-DEPLOY | Deploy to prod + runbook | [ ] | All gate tasks | YES |
| 4A | Process your own TikTok export through prod | [ ] | 4-DEPLOY | YES |
| 4A+ | Re-test after Tier 2 completes | [ ] | 1D+, 4A | NO |
| 4B | Process second test account | [ ] | 4A | YES |
| 4C | Write tester onboarding message | [ ] | 2E-tt | YES |
| 4D | Invite first 5 friends | [ ] | 4A-4C | YES |
| 4E | Observe + fix top 3 issues | [ ] | 4D, 3A | — |
| 4F | Invite remaining friends | [ ] | 4E | — |

**4-DEPLOY** — Runbook, not code. Deployment checklist for every service, env var, migration, and smoke test.

---

## Completed Work Not In Original Plan

| What | PR / Location | Detail |
|------|--------------|--------|
| Email/password auth + settings page | PR #104 | Full auth beyond Google OAuth: login form, password reset, email verification, settings page, account deletion, dev quick-login |
| Local dev mode / inline pipeline | PR #109 | Zero API keys needed. Pipeline runs inline via BackgroundTasks when SQS_QUEUE_URL absent. Fake Apify/Gemini/OpenAI fallbacks. |
| HTTP retry for entity resolvers | PR #106 | Exponential backoff (1/2/4s) on 429/5xx for Maps, Books, TMDB, Spotify. Respects Retry-After header. |
| Research sprint + 6 experiments | PR #116 | Apify profiling, vision analysis, pipeline v3 unit economics, golden set (106 items), agent eval, TikWM benchmark |
| 8-facet ontology | `app/services/ontology.py` | 111 tier-1 labels across 8 facets. validate_classification() handles v1/v2 formats. format_ontology_for_prompt() for cache-friendly injection. |
| Backfill script | `workbench/tools/backfill_v2.py` | Re-process existing items with v2 prompts. Supports --dry-run. |
| 11 Alembic migrations | `alembic/versions/` | Latest: 011_add_video_url_comments (video URLs + top comments for pipeline v2) |

## In-Flight Branches

| Branch | Commits | Status |
|--------|---------|--------|
| `s0shaheen/pipeline-v2-prompts` | 3 ahead of main | Wires v2 prompts into perceive/classify steps. Needs PR + merge. |
| `s0shaheen/tikwm-primary-enrichment` | 1 ahead of main | TikWM primary enrichment, Apify fallback. Issue #123. Needs rebase + PR. |
