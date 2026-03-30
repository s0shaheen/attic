# Attic Friends Alpha — Tracker

**Goal:** Ship the full experience to 15-20 friends.
**Gate:** All `YES` tasks complete and deployed. `NO` tasks can ship after first invites.

---

`[ ]` Not started · `[~]` Planned · `[>]` In progress · `[x]` Done · `[!]` Blocked

## Layer 0: Foundations

| ID | Task | Status | Depends on | Gate? |
|----|------|--------|------------|-------|
| 0A | Agent prompt port + SSE protocol | [ ] | — | YES |
| 0B | Prompt versioning system | [ ] | — | YES |
| 0C | Collections DB migration | [ ] | — | YES |
| 0D | RLS hardening + negative tests | [ ] | — | YES |

**0A** — CRITICAL PATH. Port the refined v3 prompts from the workbench into the production agent. The workbench has two pipeline variants: a two-pass (perception + classification) and a single-pass Tier 1 for upload-time. The production pipeline currently does parse→enrich→subtitle→embed with no Gemini classification. Also define the SSE event contract for structured responses — currently chat only streams text tokens, but entity cards, thumbnail grids, and editorial asides need their own event types.

**0B** — Extract prompts into a versioned directory loaded at startup. Do alongside 0A.

**0C** — New tables for collections and collection membership. Models, migration with downgrade, RLS policies. Decisions about schema design (source types, relationship to uploads, metadata) should be surfaced during planning.

**0D** — Verify every table has correct RLS policies. Negative tests proving user A can't see user B's data. Ethics gate.

## Layer 1: Backend

| ID | Task | Status | Depends on | Gate? |
|----|------|--------|------------|-------|
| 1A | Auto-collection generation | [~] DEFERRED | 0A, 0C | NO |
| 1B | Instagram parser | [ ] | — | NO |
| 1C | Instagram pipeline + collection import | [ ] | 1B, 0C | NO |
| 1D | Background Tier 2 processing | [ ] | 0A | NO |
| 1E | Spotify integration | [ ] | 0A | NO |
| 1F | Email notification on processing complete | [ ] | — | YES |
| 1G | Rate limiting + error handling | [ ] | — | YES |
| 1H | Collection-from-chat agent tool | [ ] | 0C, 0A | NO |

**1A** — DEFERRED. Rule-based entity grouping was implemented and tested against 1334 real IG posts but produced too many false positives even with intent-based filtering (primary entity + actionable viewer_orientation). Needs a fundamentally different approach — likely LLM-driven per-item collection assignment rather than entity-type grouping. Demoted from gate to non-gate. Collections remain available via manual, agent, and import modes.

**1B** — Instagram exports are structurally different: folder-based not ZIP, different JSON schemas, and pre-existing user collections as separate files. Decisions about how IG data maps to the existing media event schema should be surfaced.

**1C** — Wire Instagram parser into upload flow and pipeline. Different Apify actor. Import pre-existing IG collections so they appear in library immediately before AI processing.

**1D** — After Tier 1, kick off the full two-pass pipeline in background. Overwrites Tier 1 data. Decisions about triggering, queue design, and agent handling of mixed Tier 1/Tier 2 data.

**1E** — Spotify OAuth + playlist creation from music entities. CSV fallback for other integrations.

**1F** — Email via Resend when pipeline finishes.

**1G** — Per-user rate limits. Backoff on 429s. SSE error recovery. GitHub issues #70, #71.

**1H** — New agent tool for saving chat results as a collection. Needs product decisions about UX first.

## Layer 2: Frontend

| ID | Task | Status | Depends on | Gate? |
|----|------|--------|------------|-------|
| 2A | Apply brand kit to all screens | [ ] | — | YES |
| 2B | Chat page rebuild | [ ] | 0A, 2A | YES |
| 2C | Library view + API endpoints | [ ] | 0C, 1A, 2A | YES |
| 2D | Processing page | [ ] | 1F, 2A | YES |
| 2E-tt | Upload walkthrough — TikTok | [ ] | 2A | YES |
| 2E-ig | Upload walkthrough — Instagram | [ ] | 1B | NO |
| 2F | Instagram collection display | [ ] | 1C, 2C | NO |
| 2G | Conversation history | [ ] | 2B | YES |
| 2H | Mobile responsiveness | [ ] | 2B, 2C | YES |
| 2I | Empty states | [ ] | 2B, 2C | YES |
| 2J | Feedback mechanism | [ ] | 2B | YES |

**2A** — Reskin all existing screens with Parchment + Ink. Design tokens and component specs exist in the repo.

**2B** — Core product screen. Entity cards, sidebar, editorial asides, thumbnail grids, streaming indicator. Full-stack: consumes 0A's SSE contract. Needs product decisions about rendering with real data. Component specs and wireframes exist in design docs.

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
| 3G | Cost controls | [ ] | 1G | YES |
| 3H | Data deletion cascade verification | [ ] | 0C | YES |

**3E** — Graceful degradation when external APIs are down. Each pipeline step and agent tool needs a failure path.

**3H** — Verify delete account cascades through all tables including collections. Test with full user data.

## Layer 4: Deploy & Validate

| ID | Task | Status | Depends on | Gate? |
|----|------|--------|------------|-------|
| 4-DEPLOY | Deploy to prod + runbook | [ ] | All gate tasks | YES |
| 4A | Process your own TikTok export through prod | [ ] | 4-DEPLOY | YES |
| 4A+ | Re-test after Tier 2 completes | [ ] | 1D, 4A | NO |
| 4B | Process second test account | [ ] | 4A | YES |
| 4C | Write tester onboarding message | [ ] | 2E-tt | YES |
| 4D | Invite first 5 friends | [ ] | 4A-4C | YES |
| 4E | Observe + fix top 3 issues | [ ] | 4D, 3A | — |
| 4F | Invite remaining friends | [ ] | 4E | — |

**4-DEPLOY** — Runbook, not code. Deployment checklist for every service, env var, migration, and smoke test.
