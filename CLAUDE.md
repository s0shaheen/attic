# Attic — Claude Code Reference

## What Attic Is

Attic is a personal content intelligence platform. Users upload TikTok data exports (ZIP files containing liked/favorited video metadata). Attic classifies, organizes, and makes this content searchable through an agentic chat interface. The product's value lives in the quality of its classification, retrieval, and conversational responses — not in the web UI, which is a delivery vehicle.

## What Matters

The intelligence layer determines whether this product succeeds or fails. When making decisions, prioritize in this order:

1. **Classification quality** — are the 8 ontology facets correct for a given video?
2. **Retrieval quality** — does the agent find the right videos for a query?
3. **Agent response quality** — is the conversational answer helpful, specific, and delightful?
4. **User experience** — does the UI feel good and the brand feel right?
5. **Infrastructure** — does the plumbing work?

Never build infrastructure that doesn't directly improve one of the first three.

---

## Issue Tracking (MANDATORY — read before any work)

**Every PR MUST reference an issue with `Closes #N`. If no issue exists, create one first.**

**TL;DR — 4 rules that keep tracking in sync automatically:**
1. **Before writing code:** move the issue to the In Progress board column
2. **Every PR:** include `Closes #N` in the body — this auto-closes the issue on merge
3. **Specs from eng review:** paste the full spec into a GitHub issue comment (not a local file)
4. **Session end:** verify all issues you touched have correct board column

**Board:** [GitHub Project Board](https://github.com/users/s0shaheen/projects/2) — Backlog | Up Next | In Progress | Paused | Done

**Quick filters:**
```bash
gh issue list --label ready                      # Ready to implement
gh issue list --label p0-critical,p1-high         # Urgent items
gh issue list --label needs-decision              # Waiting on founder
```

### Session Start Checks

At the start of every session, run these checks:
1. Read `CLAUDE.md` + `docs/CURRENT_PLAN.md`
2. Install dependencies:
   ```bash
   cd src/frontend && npm install --silent && cd ../..
   cd src/backend && uv sync --all-extras --quiet && cd ../..
   ```
3. Check for orphaned In Progress issues: are there issues in In Progress that don't match the current workspace's branch? If found, ask the user whether to move them to Paused or back to Up Next.
4. Quick board health: `gh issue list --search "label:ready label:p0-critical label:p1-high" --state open` — flag anything urgent.

### Sync Points

| When this happens... | ...do this automatically |
|---|---|
| **You start working on an issue** | Move to In Progress column. Do this BEFORE writing any code. |
| **You create a branch** | Name it `s0shaheen/issue-N-short-desc`. GitHub auto-links it. |
| **You create a PR** | Include `Closes #N` in the PR body. Non-negotiable. |
| **An eng review produces a spec** | Paste the full spec into an issue comment. Move issue to Up Next. |
| **A CEO review defers an item** | Create issue with `deferred` label OR comment on existing issue. |
| **Scope changes mid-implementation** | Comment on the issue with what changed and why. |
| **You discover a blocker** | Comment on the issue. Add `blocked` label. |
| **You discover a new task** | Create a new issue — do NOT silently expand current scope. Link with "Discovered while working on #N". |
| **A decision is made** | Comment on the issue with the decision and rationale. |
| **You finish a session** | Verify every issue you touched has correct board column. |

### Before Creating Any Issue

1. Search existing open issues: `gh issue list --search "KEYWORDS" --state open`
2. If a match exists, classify the relationship:
   - **Subset** → add as comment or checklist item on existing issue
   - **Supersedes** → close old with comment linking to new
   - **Conflicts** → present both to the user, ask which approach
   - **Adjacent** → create new issue, note the relationship
3. If no match, create the issue

### Issue Template

```markdown
## What
[One sentence — what changes]

## Why
[User-facing impact or technical necessity]

## Acceptance Criteria
- [ ] specific verifiable thing
- [ ] specific verifiable thing
- [ ] Tests pass

## Files Touched
[List files — use "NEW: path" for new files]

## Not In Scope
[Explicit boundaries]
```

### Labels (4 dimensions)

- **Priority**: `p0-critical`, `p1-high`, `p2-medium`, `p3-low`, `p4-someday`
- **Readiness**: `ready` (spec'd, unblocked), `needs-spec` (needs eng review), `needs-decision` (founder must choose), `needs-data` (requires production data)
- **Autonomy**: `autonomous` (agent can implement without asking), `guided` (needs founder input during work), `founder-only` (only the founder can do this)
- **Component**: `backend`, `frontend`, `agent`, `pipeline`, `infra`, `security`

### Board Columns

- **Backlog**: Ideas, deferred, `needs-spec`, `needs-decision`, `needs-data`
- **Up Next**: `ready` — has spec or is simple enough, all decisions made, dependencies merged
- **In Progress**: Currently being worked on
- **Paused**: Work that was started but stopped — deprioritized or explicitly paused
- **Done**: PR merged and closed

### Context Handoff

When ending a session:
1. Verify every issue you touched has correct board column
2. Note any blockers or decisions needed as issue comments
3. The new session reads `CLAUDE.md` + `docs/CURRENT_PLAN.md` to resume

---

## Architecture

```
Browser (Next.js) ──SSE──► FastAPI ──► Agent Loop (Claude Haiku 4.5)
                                         ├─ query_items (SQLAlchemy)
                                         ├─ classify (Gemini Flash)
                                         ├─ analyze_visual (Gemini Flash + grounding)
                                         ├─ search_similar (pgvector cosine)
                                         ├─ get_stats (aggregate queries)
                                         └─ resolve_entity (Maps/Books/TMDB/Spotify)
                                       All results cached → media_events DB

SQS → Lambda: parse_export → apify_enrich → subtitle_fetch → embed
               (runs once per upload, 4 sequential steps)
```

### Stack

| Layer | Technologies |
|-------|-------------|
| **Auth** | Supabase Auth (Google OAuth + Email/Password) |
| **Database** | Supabase PostgreSQL + pgvector, SQLAlchemy 2.0, Alembic |
| **Backend** | Python 3.13, FastAPI |
| **Frontend** | Next.js 14, TypeScript, Tailwind, shadcn/ui (rebuilding) |
| **File Upload** | Uppy + Supabase Storage |
| **Pipeline** | AWS SQS + single Lambda (4 steps: parse→apify→subtitle→embed) |
| **Real-time** | Supabase Realtime |
| **Notifications** | Resend (email) |
| **Observability** | Sentry (errors), PostHog (analytics) |
| **Hosting** | Vercel (frontend), Render (API) |

### LLM Stack

| Model | Role | Module |
|-------|------|--------|
| Claude Haiku 4.5 | Agent orchestrator — tool calling, reasoning, response generation | `app/services/agent.py` |
| Gemini Flash | Classification (8-facet ontology) + visual analysis + Google Search grounding | `app/services/gemini.py` |
| OpenAI text-embedding-3-small | 1536-dim embeddings for semantic search (pgvector) | Pipeline step 4 |
| Direct API wrappers | Entity resolution — Google Maps, Google Books, TMDB, Spotify | `app/services/entity_resolvers.py` |

### Agent Layer

Manual tool loop (~50 lines, Anthropic SDK). No frameworks.

- Tools return `AgentToolResult(success, data, error, partial_data)` — **never raise**
- All tool results cached to DB inline (upsert before returning to agent loop)
- System prompt built by `app/services/prompts.py` — includes ontology, user data summary, query plan templates
- SSE streaming to frontend via `app/routers/chat.py`

### Ontology (Two-Tier Labels)

8 orthogonal facets, each with a fixed tier-1 vocabulary and open tier-2 micro-labels:

| Facet | Purpose | Example Tier-1 Labels |
|-------|---------|----------------------|
| Affect | Emotional tone | funny, wholesome, sad, nostalgic, satisfying |
| Topic | Subject matter | food, fashion, comedy, technology, pets |
| Genre | Content format | tutorial, vlog, skit, recipe, asmr, meme |
| Communicative Intent | Creator's goal | entertain, inform, persuade, sell, document |
| Creator Role | Who made it | professional, amateur, brand, influencer |
| Viewer Orientation | Why user saved it | passive_consumption, active_learning, shopping_research |
| Presentation Style | Visual format | talking_head, voiceover, text_overlay, cinematic |
| Content Provenance | Origin | original, repost, duet, stitch, remix |

- **Tier-1**: Validated against `ONTOLOGY_V1` dict in `ontology.py`. Drives collections and aggregation.
- **Tier-2**: Free-form micro-labels from Gemini. Drives discovery and future ontology evolution.
- **Validation**: All classification output passes through `validate_classification()` which maps invalid labels to tier-2 and assigns fallbacks.

### Media Types

| Type | `media_type` | Pipeline |
|------|-------------|----------|
| Video | `video` | Full pipeline (subtitles from Apify) |
| Image | `image` | Skip subtitle step |
| Slideshow | `slideshow` | Skip subtitle step, `image_count` + `image_urls` fields |

### Pipeline

4-step pipeline, SQS + single Lambda, runs once per upload:

1. `PARSE_EXPORT` — Extract URLs from ZIP, create `media_event` rows
2. `APIFY_ENRICH` — Fetch TikTok metadata (batched, 50/call)
3. `SUBTITLE_FETCH` — Get subtitles from Apify data
4. `EMBEDDING` — Fuse text + generate 1536-dim vectors (batched, 100/call)

**All Lambda functions MUST be idempotent.** Use upserts and deterministic IDs.

---

## Key Files

### Agent Intelligence (the core product)
```
app/services/agent.py              — Agent loop, tool dispatch
app/services/agent_tools.py        — Tool implementations (query, classify, visual, entity, stats, search)
app/services/gemini.py             — Gemini Flash client (classify + analyze_visual)
app/services/ontology.py           — ONTOLOGY_V1 dict, validate_classification(), format_ontology_for_prompt()
app/services/prompts.py            — System prompt builder (build_system_prompt, query plan templates)
app/services/entity_resolvers.py   — Google Maps, Books, TMDB, Spotify API wrappers
```

### Infrastructure
```
app/routers/chat.py                — Chat SSE endpoint
app/routers/uploads.py             — Upload endpoints
app/core/auth.py                   — JWT validation
app/config.py                      — Settings
app/models/media_event.py          — Core data model (50+ columns)
src/lambdas/pipeline/handler.py    — Unified pipeline Lambda
```

### Workbench (AI development lab)
```
workbench/README.md                             — Experiment index + cumulative learnings
workbench/tools/classify_batch.py               — Batch classification with structured output
workbench/tools/run_evals.py                    — Golden set accuracy evaluation (per-facet)
workbench/tools/generate_test_data.py           — Synthetic test case generator via Claude
workbench/tools/seed_db.py                      — Database seeding for local dev
workbench/experiments/01-apify-profiling/        — Data quality + Apify validation
workbench/experiments/02-vision-analysis/        — Thumbnail vs video, prompt variants
workbench/experiments/03-pipeline-v3/            — Two-pass pipeline, Tier 1, search, economics
workbench/experiments/04-golden-set/             — Ground-truth evaluation infrastructure
workbench/notebooks/                            — Interactive exploration (01-06)
workbench/data/                                 — Shared raw inputs (favorites, Apify output)
```

### Brand & Frontend
```
docs/BRAND.md                      — Authoritative brand identity (Parchment + Ink)
src/frontend/src/lib/design-tokens.ts — Machine-readable token source of truth
src/frontend/src/app/globals.css   — CSS custom properties consuming tokens
src/frontend/src/app/layout.tsx    — Font loading (Crimson Pro, DM Sans, DM Mono)
```

### Config
```
.env.master                        — Single source of truth for all secrets (gitignored)
.env.master.example                — Template (committed)
scripts/setup-env.sh               — Generates all derived env files
scripts/check-env.sh               — Validates env completeness
```

### Reference Docs
```
docs/CURRENT_PLAN.md               — Architecture decisions reference
docs/CEO_PLAN_REVIEW_2026-03-14.md — Architecture decision record
```

---

## Development Environment

### Setup

Single Python venv at repo root (NOT in `src/backend/`):
```bash
.venv/bin/python    # Used by backend, workbench, and eval scripts
```

Single secret source:
```bash
.env.master         # All API keys and config — generates everything else
./scripts/setup-env.sh  # Creates src/backend/.env, src/frontend/.env.local, workbench/.env
```

### Database

Default: Supabase Cloud (always on, no Docker needed)
Optional: Local Supabase via `supabase start` (for migration work or full resets)


### Primary IDE: VS Code + Claude Code

Terminal layout:
- **Terminal 1**: Claude Code (main working session)
- **Terminal 2**: Shell (scripts, git, quick checks)
- **Terminal 3**: Servers (only when full-stack testing)

### Running Locally

```bash
# Workbench (no infrastructure needed)
.venv/bin/python workbench/tools/classify_batch.py workbench/data/sample-videos.json --limit 5
.venv/bin/python workbench/tools/run_evals.py --verbose --save
.venv/bin/python workbench/tools/generate_test_data.py "cooking videos with emoji captions" --count 10

# Database seeding (requires Supabase reachable)
./scripts/seed-db.sh

# Environment setup
./scripts/setup-env.sh
./scripts/check-env.sh

# Full stack (Supabase Cloud is always on, no Docker needed for database)
./scripts/dev-start.sh
# Test account: test@attic.to / testpassword123
# Supabase dashboard: https://supabase.com/dashboard
# Optional: ./scripts/dev-start.sh --with-localstack  (for S3/SQS pipeline testing, requires Docker)

# Backend only
cd src/backend && ../../.venv/bin/uvicorn app.main:app --port 8000 --reload

# Frontend only
cd src/frontend && npm run dev

# Tests
cd src/backend && ../../.venv/bin/pytest tests/ -v --tb=short
cd src/frontend && npm run typecheck && npm run lint && npm run build

# Lint
cd src/backend && ../../.venv/bin/ruff check . && ../../.venv/bin/ruff format .
```

---

## Custom Commands

### Daily workflow
| Command | Purpose |
|---------|---------|
| `/commit "desc"` | Smart commit — analyzes changes, splits into logical commits, pushes |
| `/land "desc"` | Full ship — commit + test + push + PR with `Closes #N` |
| `/review` | Layered code review — auto-detects backend, agent, frontend, DB layers |
| `/wrapup` | Session handoff — conversation flow, changes, state, next steps |

### Quality & testing
| Command | Purpose |
|---------|---------|
| `/test` | Smart test runner — detects what changed, runs relevant tests |
| `/eval` | Classification evals against golden set with per-facet accuracy |
| `/status` | Project health dashboard — git, tests, lint, env, eval status |

### Infrastructure
| Command | Purpose |
|---------|---------|
| `/start` | Launch full local stack with health checks and seeded data |
| `/resolve-conflicts` | Rebase on main with file-type-aware resolution |
| `/issue "desc"` | Create well-formed GitHub issue with quality gate |

### Typical session flow
```
/status → work → /commit "save progress" → ... → /review → /land "description" → /wrapup
```

---

## Code Conventions

### Python (Backend + Workbench)

- Type hints required on all functions
- `async def` for all I/O operations (HTTP, DB, file)
- Pydantic models for all request/response schemas
- Result objects for service returns — **never raise for business logic**
- Dependency injection via FastAPI `Depends()`
- Agent tools return `AgentToolResult` — never raise
- All external API calls must have explicit timeouts
- Logging: structured dicts, no PII (no user content, tokens, emails, raw URLs)

### TypeScript (Frontend)

- Strict mode enabled
- Zod for runtime validation
- Server components by default, `"use client"` only when hooks are needed
- TanStack Query for server data fetching

### Database

- All schema changes via Alembic migrations
- **Never raw SQL** — SQLAlchemy ORM exclusively
- RLS policies on all user-owned tables
- Upserts for any write that could be retried (idempotency)

### Git

- Branch naming: `s0shaheen/issue-N-short-desc` or `s0shaheen/short-desc`
- Commits: `feat(scope): description` (conventional commits)
- Scopes: `agent`, `frontend`, `pipeline`, `api`, `db`, `env`, `workbench`, `dx`, `docs`, `test`
- PRs closing an issue: include `Closes #N` in body

### Versioning

- **VERSION is bumped at ship time only** — never in feature branches
- Feature branches add changelog entries under `## [Unreleased]` in CHANGELOG.md
- `/land` moves Unreleased entries into a versioned section and bumps VERSION
- This prevents merge conflicts when multiple branches ship in parallel

### Testing

- Every public function must have tests
- Mock all external services (Anthropic, Gemini, Apify, OpenAI, entity APIs)
- Test naming: `test_{function}_{scenario}_{expected}`
- Agent tools: test cache hit/miss, timeout handling, invalid responses, error result paths
- Test edge cases and error paths — not just happy paths

```python
# Good test name
def test_classify_gemini_timeout_returns_error_result():
    ...

# Bad test name
def test_classify():
    ...
```

---

## Brand & Design System

**Reference**: `docs/BRAND.md` is the authoritative source. Key rules below.

### Philosophy
The UI is the frame. User content is the art. All visual saturation belongs to the user's TikTok thumbnails. The chrome recedes.

### Colors: Parchment + Ink

**All colors must use CSS custom property tokens.** Never hardcode hex values.

| Token | Hex | Usage |
|-------|-----|-------|
| Parchment | `#F8F7F4` | Page background |
| White | `#FFFFFF` | Card/surface backgrounds |
| Ink | `#1C1B18` | Primary text |
| Soft Black | `#2C2926` | User message bubbles |
| Stone | `#9C9890` | Secondary/muted text |
| Border | `#E6E4DE` | Dividers, card borders |
| Subtle | `#F0EEE8` | Chips, tags, hover fills |

### Cinnamon Accent — RESTRICTED

Cinnamon (`#A06840`) exists for special moments only:
- **ALLOWED**: Landing hero, primary CTAs (marketing), reveal stats, badges, onboarding, focus rings
- **BANNED**: Chat bubbles, entity cards, nav, everyday chips, collections, settings, upload

If you're writing product UI (not marketing/landing), **do not use Cinnamon**.

### Typography

| Font | Role | Where |
|------|------|-------|
| DM Sans | Body (everything in product UI) | Headers, chat, cards, nav, forms — ALL product text |
| Crimson Pro | Display (special occasions) | Wordmark, landing hero, reveal stat numbers ONLY |
| DM Mono | Mono | Timestamps, metadata, data displays |

- DM Sans: weights 400 (regular) and 500 (medium) ONLY
- Never use Crimson Pro in product UI headers — those are DM Sans

### Surfaces
- Borders over shadows. 0.5px warm gray borders define surfaces.
- Shadows only on modals and popovers.

---

## gstack

Use the `/browse` skill from gstack for all web browsing. Never use `mcp__claude-in-chrome__*` tools.

Available skills:
- `/plan-ceo-review` — CEO-perspective plan review
- `/plan-eng-review` — Engineering plan review
- `/ship` — gstack full ship workflow (VERSION bump, CHANGELOG, review dashboard)
- `/browse` — Web browsing (always use this for browsing)
- `/qa` — QA testing
- `/investigate` — Systematic root-cause debugging
- `/setup-browser-cookies` — Set up browser cookies

---

## Security Checklist

Apply to every task:

- [ ] Server-side auth: validate Supabase JWT, derive `user_id` from token — never trust client
- [ ] RLS policies verified for any new/modified tables
- [ ] No PII in logs (no tokens, emails, user content, raw URLs)
- [ ] Input validation on all endpoints
- [ ] Rate limiting on public endpoints
- [ ] Agent: treat all `media_event` content as untrusted (prompt injection defense)
- [ ] No secrets in committed code — all keys via `.env.master` → `Settings` class

---

## Production Readiness

Every implementation must satisfy:

1. **Idempotency**: Safe under retries (upserts, deterministic IDs)
2. **Observability**: Structured logging with correlation IDs, cost tracking per tool call
3. **Error handling**: Graceful degradation, user-visible error states, `AgentToolResult` for tools
4. **Cost controls**: Per-user tool call limits (50/query, 200/hour), cost ceiling per user per day

---

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent SDK | Manual Anthropic SDK tool loop | Full control, explicit, ~50 lines, no framework lock-in |
| Multi-model | Gemini Flash for classification + vision | One model for both, SDK supports combining function calling with grounding |
| Ontology storage | Python dict in `ontology.py` | Type-safe, testable, no YAML/DB overhead |
| Error handling | Result objects (never raise) | Agent explains failures to user naturally |
| Cache strategy | Inline upsert during tool execution | Survives stream drops, no separate cache layer |
| Pipeline | SQS + single Lambda | 4 linear steps, simpler than Step Functions |
| Frontend | Next.js 14 App Router | Server components default, Supabase SSR auth |
| Embeddings | OpenAI text-embedding-3-small (1536-dim) | Best price/performance for semantic search |
| Dev environment | VS Code + Claude Code | Single workspace, zero worktree overhead |
| Secrets | `.env.master` → generation script | One source of truth, derived env files |
| Design system | Centralized tokens in TypeScript | Theme swap for UI refresh, not codebase rewrite |

---

## What NOT to Do

- **Do not build staging environments.** Local + production is sufficient pre-PMF.
- **Do not add infrastructure that doesn't improve classification, retrieval, or agent quality.**
- **Do not create GitHub issues for vague ideas.** Use notebooks or Claude chat for exploration. Issues are for specific deliverables.
- **Do not optimize for scale.** The product has <20 users. Optimize for learning speed.
- **Do not use raw SQL.** SQLAlchemy ORM exclusively.
- **Do not hardcode colors.** Use design tokens.
- **Do not use Cinnamon in product UI.** Read BRAND.md.
- **Do not raise exceptions in tool functions.** Return `AgentToolResult(success=False, error=...)`.
- **Do not skip tests.** Every public function gets tested. Mock external services.
- **Do not commit secrets.** Everything flows from `.env.master`.
