# Attic — Claude Code Reference

## What Attic Is

Personal content intelligence platform. Users upload TikTok/Instagram data exports; Attic classifies, organizes, and makes content searchable through an agentic chat interface. Product value = classification + retrieval + agent response quality — not the UI.

**Priority order:** Classification quality → Retrieval quality → Agent response quality → UX → Infrastructure. Never build infrastructure that doesn't improve the first three.

## Active Plan

`docs/ALPHA_TRACKER.md` — the alpha launch tracker. Read at session start alongside this file.

---

## Issue Tracking

**Every PR MUST include `Closes #N`.** No issue? Create one first.

1. Move issue to In Progress **before** writing code
2. Every PR body includes `Closes #N`
3. Specs go in GitHub issue comments, not local files
4. Session end: verify all touched issues have correct board column
5. New tasks discovered during work → new issue, don't expand scope. Link with "Discovered while working on #N"

**Board:** [GitHub Project Board](https://github.com/users/s0shaheen/projects/2) — Backlog | Up Next | In Progress | Paused | Done

**Labels** — Priority: `p0-critical` `p1-high` `p2-medium` `p3-low` `p4-someday` · Readiness: `ready` `needs-spec` `needs-decision` `needs-data` · Autonomy: `autonomous` `guided` `founder-only` · Component: `backend` `frontend` `agent` `pipeline` `infra` `security`

**Branch naming:** `s0shaheen/issue-N-short-desc`

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

SQS → Lambda: parse_export → apify_enrich → subtitle_fetch → perceive → classify → embed
```

| Component | Tech |
|-----------|------|
| Agent | Manual Anthropic SDK tool loop (~50 lines, no frameworks) |
| Classification | Gemini Flash — 8-facet ontology (see `app/services/ontology.py`) |
| Embeddings | OpenAI text-embedding-3-small (1536-dim, pgvector) |
| Auth | Supabase Auth (Google OAuth + Email/Password) |
| DB | Supabase PostgreSQL, SQLAlchemy 2.0, Alembic |
| Frontend | Next.js 14, TypeScript, Tailwind, shadcn/ui |
| Pipeline | AWS SQS + single Lambda (6 steps, idempotent, upserts) |
| Hosting | Vercel (frontend), Render (API) |
| Observability | Sentry (errors), PostHog (analytics) |

---

## Code Conventions

### Python
- Type hints on all functions. `async def` for all I/O.
- **Result objects, never raise for business logic.** Agent tools return `AgentToolResult(success, data, error, partial_data)`.
- External API calls: explicit timeouts. Dependency injection via `Depends()`.
- Logging: structured dicts, **no PII** (no tokens, emails, user content, raw URLs).

### TypeScript
- Strict mode. Zod for runtime validation. Server components by default.

### Database
- Schema changes via Alembic only. **Never raw SQL** — SQLAlchemy ORM exclusively.
- RLS policies on all user-owned tables. Upserts for idempotency.

### Git
- Commits: `feat(scope): description` — scopes: `agent` `frontend` `pipeline` `api` `db` `env` `workbench` `dx` `docs` `test`
- VERSION bumped at ship time only, never in feature branches

### Testing
- Every public function gets tests. Mock all external services.
- Naming: `test_{function}_{scenario}_{expected}`. Test error paths, not just happy paths.

---

## Security

- Validate Supabase JWT server-side, derive `user_id` from token — never trust client
- RLS policies on all user-owned tables
- No PII in logs. No secrets in code — all via `.env.master` → `Settings`
- Input validation + rate limiting on all public endpoints
- Agent: treat all `media_event` content as untrusted (prompt injection defense)

---

## Running Locally

```bash
# Environment
.env.master              # Single source of truth for all secrets
./scripts/setup-env.sh   # Generates derived .env files
.venv/bin/python         # Single venv at repo root

# Full stack
./scripts/dev-start.sh   # Test: test@attic.to / testpassword123

# Backend / Frontend only
cd src/backend && ../../.venv/bin/uvicorn app.main:app --port 8000 --reload
cd src/frontend && npm run dev

# Tests + lint
cd src/backend && ../../.venv/bin/pytest tests/ -v --tb=short
cd src/backend && ../../.venv/bin/ruff check . && ../../.venv/bin/ruff format .
cd src/frontend && npm run typecheck && npm run lint && npm run build

# Workbench
.venv/bin/python workbench/tools/run_evals.py --verbose --save
.venv/bin/python workbench/tools/classify_batch.py workbench/data/sample-videos.json --limit 5
```

---

## Brand

See `docs/BRAND.md` for full spec. Key rules:
- **Parchment + Ink palette.** All colors via CSS tokens. Never hardcode hex.
- **Cinnamon (`#A06840`) is restricted** — marketing/landing only, banned in product UI.
- **DM Sans** for all product text. **Crimson Pro** for wordmark/landing only. **DM Mono** for data.
- Borders over shadows. UI is the frame; user content is the art.

---

## What NOT to Do

- Don't build staging environments or optimize for scale (<20 users)
- Don't add infrastructure that doesn't improve classification/retrieval/agent quality
- Don't use raw SQL, hardcode colors, or use Cinnamon in product UI
- Don't raise in tool functions — return `AgentToolResult(success=False, error=...)`
- Don't skip tests or commit secrets
- Don't create issues for vague ideas — issues are for specific deliverables

---

## Reference

- `docs/ALPHA_TRACKER.md` — Active alpha plan
- `docs/BRAND.md` — Brand identity spec
- `docs/archive/` — Historical plans, setup docs, decision records
