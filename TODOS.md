# TODOS

Deferred work items captured during engineering review (2026-03-15).

## TODO 1: Video cards with structured SSE events
- **What:** Add `"items"` SSE event type carrying structured media data (thumbnail, caption, creator, canonical_url). Frontend renders as visual cards.
- **Why:** Markdown links are functional but not visually compelling. Cards with thumbnails make the experience app-like.
- **Depends on:** Tasks 3-4 from founder-testable plan shipping first. Revisit after founder testing reveals whether markdown + links feels insufficient.
- **Where to start:** `agent.py` (emit items SSE event from tool results) → `chat/page.tsx` (card component).

## TODO 2: Pipeline failure feedback to user
- **What:** Surface pipeline processing status/errors to the user (banner on chat page: "processing..." / "failed").
- **Why:** After `/process` returns 202, if Lambda fails, user sees nothing in chat with no explanation. Silent failure = worst UX.
- **Depends on:** Upload record status field updated by Lambda. Could use Supabase Realtime or polling.
- **Where to start:** Check Upload model `status` field. Add GET `/api/uploads/status` endpoint or use Supabase Realtime channel.

## TODO 3: pgvector HNSW index on embedding_vector
- **What:** Add HNSW index via Alembic migration for O(log n) vector search.
- **Why:** Sequential scan is fine for <10K items but will degrade at scale. Single migration.
- **Depends on:** `search_similar` tool shipping first.
- **Where to start:** `alembic revision --autogenerate -m "add hnsw index on embedding_vector"`

## TODO 4: Frontend component test infrastructure
- **What:** Set up Vitest + React Testing Library. Add component tests for key UI (messages, starters, upload).
- **Why:** Currently only 1 smoke test + SSE parser tests. As frontend grows, component tests prevent regressions.
- **Depends on:** Nothing — can be added anytime.
- **Where to start:** `npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom`

## TODO 5: Prompt regression eval suite
- **What:** Minimal eval for system prompt quality: 5-10 representative queries with expected tool call patterns (e.g., "what books have I saved?" should trigger query_items then analyze_visual on low-text results).
- **Why:** The system prompt is the #1 product differentiator. Changes can silently regress entity retrieval quality. No automated check exists today.
- **Depends on:** Wave 5.1 (system prompt rewrite) shipped. Stepping stone toward full eval infra (task 8.4 in TODO.md).
- **Where to start:** `tests/eval/` dir or extend `tests/unit/test_prompts.py`. Define expected tool call sequences per query type, mock Claude responses to verify the agent follows plan templates.
