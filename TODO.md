# Attic — TODOs

**Last updated:** 2026-03-15
**Prioritization:** P0 = must ship before launch, P1 = should ship this cycle, P2 = post-launch, P3 = gated on discovery data, P4 = someday/vision

---

## Phase 1: Ship the MVP (~8-10 days)

### System Prompt Rewrite (Wave 5.1)

**What:** New SYSTEM_PROMPT in `src/backend/app/services/prompts.py` with query intent recognition, 5 plan templates (entity retrieval, creator aggregation, simple filter, interpretive, ambiguous), disambiguation rules, recall check instruction, cost awareness. ~200 lines.

**Why:** Agent improvises strategy today (P1). 18-line prompt produces generic answers. Users get bad results for entity retrieval queries — agent searches for "book" by text and misses every video where a book appears visually.

**Context:** Current prompt at `agent.py:60-77`. Create new `prompts.py` module, import from `agent.py`. Plan templates teach the agent proven multi-step strategies. Recall check instruction: "after entity retrieval, check for low-text items that might need vision." Cost awareness: "prefer text-only first."

**Effort:** M
**Priority:** P0
**Depends on:** None

---

### Targeted Vision Prompts (Wave 5.2)

**What:** `VisionFocus` StrEnum in `gemini.py` with 5 focus modes (books, scenes, places, text, products). Each focus loads a different optimized prompt template. Update `agent_tools.py` to pass `focus` parameter. Update tool schema exposed to Claude.

**Why:** Text-first recall ceiling (P2). Books, restaurants, movies shown visually but not mentioned in captions are invisible to the agent today. Current vision prompt is 7 generic lines.

**Context:** Current prompt at `gemini.py:184-193`. Agent chooses focus based on query context (handled by system prompt plan templates from 5.1). Each focus template optimizes for specific extraction: book titles/authors/covers, movie scenes/actors, restaurant signage/locations, OCR text, product brands/packaging.

**Effort:** M
**Priority:** P0
**Depends on:** None (parallel with 5.1)

---

### RLS Hardening + Auth Boundary Tests (Wave 6.1-6.2)

**What:** Verify RLS policies on conversations, messages, and new user_credits tables. Write negative integration tests: create two users, verify user A cannot read user B's conversations/messages/credits.

**Why:** Security checklist requirement. RLS policies exist in migration 006 but have zero negative test coverage. New user_credits table needs its own RLS policy.

**Context:** RLS policies in `006_add_chat_and_classification_cache.py:108-119`. Pattern: `USING (user_id = auth.uid())` for conversations, nested subquery for messages. user_credits needs same user_id isolation.

**Effort:** M
**Priority:** P0
**Depends on:** user_credits table migration (Wave 7.1)

---

### Creator Aggregation Tool (Wave 5.3)

**What:** New `aggregate_creators` tool in `agent_tools.py`. Pure SQL GROUP BY on `creator_username` with item counts, date range, top cached topics. Register via existing `@tool` decorator.

**Why:** "Who are my top creators" currently requires fetching 50 items and counting in tokens. Wasteful and inaccurate for users with 1000+ items.

**Context:** Follow `@tool` pattern at `agent_tools.py:56`. Returns `AgentToolResult`. Consider `(user_id, creator_username)` composite index for performance on large datasets.

**Effort:** S
**Priority:** P1
**Depends on:** None

---

### Field Aggregation Tool (Wave 5.4)

**What:** New `aggregate_field` tool in `agent_tools.py`. `VALID_AGGREGATE_FIELDS = {'music_name', 'creator_username', 'media_type', 'interaction_type'}` allowlist. SQL GROUP BY + COUNT + ORDER BY count DESC.

**Why:** "What songs appear most in my saves" is unanswerable without server-side aggregation. Agent cannot GROUP BY today.

**Context:** Allowlist prevents SQL injection (field name comes from agent, which is influenced by user input). Reject invalid fields: `AgentToolResult(success=False, error="invalid field")`. Parallel with 5.3.

**Effort:** S
**Priority:** P1
**Depends on:** None (parallel with 5.3)

---

### Cost Instrumentation (Wave 5.5)

**What:** Structured cost logging in 4 files: `gemini.py` (input/output tokens), `agent.py` (Claude usage per turn), `entity_resolvers.py` (API call count per resolver), `agent_tools.py` (cache hit/miss per invocation). Plus query-level summary log at completion.

**Why:** Cannot set credit prices without real cost data (P4). Cannot debug cost issues without per-tool visibility. Feeds Phase 2 discovery (D2).

**Context:** Per-tool format: `{"event": "tool_cost", "tool": "classify", "cache_hit": false, "tokens_in": 1200, "tokens_out": 350, "estimated_cost_usd": 0.00004, "user_id": "...", "query_id": "..."}`. Query summary: `{"event": "query_complete", "query_id": "...", "total_tools": 5, "total_cost_usd": 0.003, "cache_hits": 2, "duration_ms": 4200}`. No PII in logs (no raw user queries).

**Effort:** M
**Priority:** P1
**Depends on:** None

---

### Rate Limiting Per-Tier (Wave 6.3)

**What:** Make `MAX_TOOL_CALLS_PER_QUERY` and `MAX_TOOL_CALLS_PER_HOUR` configurable per user tier. Add daily ceiling. Keep in-memory for MVP.

**Why:** Free users shouldn't have the same limits as paid users. Daily ceiling prevents runaway costs that hourly limits miss.

**Context:** Current hardcoded limits at `agent.py:57-58`. Make lookup from tier config in `tiers.py`. In-memory rate limiter is fine for single-process MVP (Render single worker).

**Effort:** S
**Priority:** P1
**Depends on:** Tier info accessible from user profile

---

### Error Handling Polish (Wave 6.5)

**What:** Entity resolver rate limit detection (HTTP 429) + exponential backoff. Conversation-not-found returns 404. Verify all tool errors produce user-friendly SSE error messages.

**Why:** Silent failures make users think the product is broken. Entity resolvers currently swallow rate limit errors. Invalid conversation IDs return no useful error.

**Context:** Entity resolvers at `entity_resolvers.py`. Chat endpoint at `chat.py`. Subsumes two prior TODO items ("Entity API rate limit handling" and "Conversation not found → 404").

**Effort:** M
**Priority:** P1
**Depends on:** None

---

### Minimal Credit System (Wave 7.1-7.4)

**What:** Alembic migration for `user_credits` table (`user_id` FK, `credit_balance` INTEGER DEFAULT 200, `credits_reset_at` TIMESTAMPTZ, `updated_at`) with RLS policy. Credit check at query start, in-memory cost accumulation during query, single atomic debit at end via `UPDATE user_credits SET credit_balance = credit_balance - :cost WHERE user_id = :uid AND credit_balance >= :cost RETURNING credit_balance`. Lazy reset: if `now() > credits_reset_at`, reset balance and advance reset_at. SSE `credits_remaining` event after each query. `CREDITS_ENABLED` env var feature flag.

**Why:** Without credits, a single heavy user can generate $50/day in API costs with no gate. Feature flag allows disabling without redeploy if bugs block users.

**Context:** Cannot add columns to Supabase `auth.users`. Atomic UPDATE prevents race conditions on concurrent queries. Lazy reset eliminates need for cron jobs. When `CREDITS_ENABLED=false`, skip check/debit and log warning.

**Effort:** M
**Priority:** P1
**Depends on:** Cost instrumentation (5.5) informs credit cost table

---

### SSE Stream Drop — Save Partial Response

**What:** Add try/finally or background task to `chat.py event_stream()` to save partial assistant message on client disconnect.

**Why:** Currently, if client disconnects mid-stream, the response is lost entirely. Only saves on `done` event.

**Context:** `chat.py` event_stream generator. Add disconnect detection and persist whatever tokens were streamed.

**Effort:** S
**Priority:** P1
**Depends on:** None

---

## Phase 1: Retained Engineering Items

### DB Upsert Constraint Violation Test

**What:** Test that cache write-back (classify, resolve_entity) logs-and-continues on constraint errors rather than crashing.

**Why:** No test coverage for this error path. A constraint violation during tool execution would surface as an unhandled error.

**Context:** Cache upserts in `agent_tools.py`. Should gracefully log and return partial data.

**Effort:** S
**Priority:** P2
**Depends on:** None

---

### Prompt Caching Verification

**What:** Verify Claude prompt caching is working — ontology prefix should be cache-hit across users. Check Anthropic dashboard metrics.

**Why:** Could save 40-60% on Claude orchestrator costs if caching is active.

**Context:** Requires Anthropic dashboard access (external to Claude Code). Check after launch with real traffic.

**Effort:** S
**Priority:** P2
**Depends on:** Launch + real traffic

---

### SSE Reconnection / Stream Drop Handling (Frontend)

**What:** Frontend auto-retry or "connection lost" UI on SSE stream drops.

**Why:** Users on flaky connections see nothing — no error, no retry.

**Context:** `chat/page.tsx:114-125` SSE handling. Add EventSource reconnection logic or visible error state.

**Effort:** S
**Priority:** P2
**Depends on:** Partial response saving (SSE stream drop item above)

---

### Split agent_tools.py if >500 Lines

**What:** Split by tool type (query tools, classification tools, aggregation tools) if file grows too large after adding 5.3/5.4.

**Why:** Maintainability — single file with 6+ tools and their schemas gets unwieldy.

**Context:** Currently ~555 lines. Adding two aggregation tools will push past 600.

**Effort:** S
**Priority:** P3
**Depends on:** 5.3 + 5.4 complete

---

### Extract Shared Package (attic_core/)

**What:** Extract SQLAlchemy models + TikTok parser into shared package if Lambda/backend code sharing gets messy.

**Why:** Currently duplicated via CommonLayer symlinks. If divergence causes bugs, extract properly.

**Context:** Deferred until needed. Current approach works for MVP.

**Effort:** M
**Priority:** P4
**Depends on:** None (defer until needed)

---

## Phase 2: Discovery (Post-Launch, gated on 20+ users)

### D1: Query Distribution Analysis

**What:** Analyze conversation logs. What % of queries are retrieval vs aggregation vs interpretive vs ambiguous? What entity types are most requested? What queries fail or produce bad results?

**Why:** Decides which system prompt plan templates to add/refine. Validates whether query strategy (5.1) is working.

**Context:** REQUIRES real user data. Manual analysis of conversation logs. Cannot be done in Claude Code. Gate: 20+ users, 5+ questions each.

**Effort:** S
**Priority:** P2
**Depends on:** Launch + 20 users with 5+ questions each

---

### D2: Cost Distribution Analysis

**What:** Analyze cost instrumentation logs. p50/p90/p99 cost per query, cost distribution by query type, per-user monthly cost by usage pattern, cache hit rate over time.

**Why:** Decides credit pricing, tier allocations, whether credit model is viable or needs restructuring.

**Context:** REQUIRES cost instrumentation (5.5) deployed + real traffic. Pull from structured logs.

**Effort:** S
**Priority:** P2
**Depends on:** Cost instrumentation (5.5) + launch + traffic

---

### D3: Recall Gap Analysis

**What:** Sample 10 users. For each, manually review their dataset and compare what the agent found vs what's actually there. Measure entity retrieval recall.

**Why:** Decides whether batch tier-1 classification (8.1) is worth building. Quantifies the text-first recall ceiling.

**Context:** REQUIRES manual human review of user datasets. Not automatable without eval infrastructure.

**Effort:** M
**Priority:** P2
**Depends on:** Launch + users

---

### D4: Ontology Fitness Check

**What:** Analyze actual user queries against ontology labels. Do users ask about things that map cleanly to facets? Which tier-1 labels get used most? What tier-2 micro-labels cluster together?

**Why:** Decides if ontology needs new facets or user-facing collection types (9.3).

**Context:** Cross-reference conversation logs with cached_classifications JSONB data.

**Effort:** S
**Priority:** P2
**Depends on:** Launch + conversation logs

---

### Evaluation Dataset V1 (8.4)

**What:** Take one real user's dataset (own test account or with permission). Manually label 100 items: entity type, genre, at least one entity per item. Run 10 representative queries. Measure precision/recall against ground truth.

**Why:** Regression test for prompt changes. Infrastructure for all future quality work. Build regardless of discovery findings.

**Context:** Becomes the baseline for evaluating system prompt changes, vision prompt improvements, and classification accuracy.

**Effort:** M
**Priority:** P2
**Depends on:** Launch (need real data to label)

---

## Phase 2: Conditional Implementation (gated on discovery)

### Batch Tier-1 Classification at Upload (8.1)

**What:** Add pipeline step: Gemini Flash-Lite text classification on every item at upload. Store tier-1 labels in `cached_classifications`. Cost: ~$0.004 per 100 items.

**Why:** Changes agent starting position from "knows nothing about your items" to "already knows topic, affect, genre of every item." Every query gets faster and more accurate.

**Context:** GATE: Build ONLY if D3 shows recall gaps >15%.

**Effort:** L
**Priority:** P3
**Depends on:** D3 recall gap analysis

---

### Pre-Estimation UX (8.2)

**What:** Show estimated cost before expensive queries, offer cheaper text-only alternative.

**Why:** Reduces surprise credit deductions and user frustration.

**Context:** GATE: Build ONLY if D2 shows users confused by credit deductions or if credit exhaustion causes churn.

**Effort:** M
**Priority:** P3
**Depends on:** D2 cost analysis + credit system (7.1-7.4)

---

### Temporal Trend Tool (8.3)

**What:** `analyze_trends(facet, granularity)` — GROUP BY time_bucket, facet_value, return time series data.

**Why:** Answers "when did I start watching cooking content" and "how have my interests changed."

**Context:** GATE: Build ONLY if D1 shows >10% of queries are temporal.

**Effort:** M
**Priority:** P3
**Depends on:** D1 query distribution analysis

---

### Credit Model Calibration (8.5)

**What:** Using real cost data from D2: set final credit-to-dollar exchange rate, per-operation credit costs, validate tier allocations against actual persona usage, decide on credit top-ups.

**Why:** The initial credit costs are guesses. Real data calibrates the pricing model.

**Context:** Requires D2 analysis complete. May result in changes to credit costs, tier allocations, and reset amounts.

**Effort:** M
**Priority:** P3
**Depends on:** D2 cost analysis data

---

## Phase 3: Build the Moat (P4, months 2-4 post-launch)

### Thumbnail Embeddings (9.1)

**What:** Run every item's thumbnail through CLIP or Gemini visual embedding model at upload. Store in pgvector alongside text embeddings. Unlocks "find more like this" for visual content without per-query vision calls.

**Why:** Fundamentally changes the edit/aesthetic content use case. Cost: ~$0.001/item at upload.

**Context:** Gate: paying users exist, D3 validates visual recall is a real gap.

**Effort:** L
**Priority:** P4
**Depends on:** D3 recall analysis, paying users

---

### Cross-Item Pattern Analysis (9.2)

**What:** Batch classification of full dataset + multi-facet aggregation + outlier detection + narrative synthesis. "What does my TikTok say about me."

**Why:** High user delight when it works. The "Wrapped" moment.

**Context:** Expensive, hard to evaluate. Only build after eval infrastructure (8.4) can measure quality.

**Effort:** XL
**Priority:** P4
**Depends on:** Eval dataset V1 (8.4), batch classification (8.1)

---

### Ontology V3: User-Facing Collection Types (9.3)

**What:** Mapping layer from user concepts ("edits", "book recs") to multi-facet queries. E.g., "edits" = genre IN (fan_creation, remix) AND presentation_style IN (cinematic, hype).

**Why:** Lets agent translate user language into multi-facet queries without users knowing about the ontology.

**Context:** Based on D4 findings. Only build after ontology fitness is validated in production.

**Effort:** L
**Priority:** P4
**Depends on:** D4 ontology fitness findings

---

### Creator Profile Enrichment (9.4)

**What:** For creators with 5+ saved items, optionally fetch Apify profile (bio, follower count, content niche). Build creator-level profiles.

**Why:** "You follow 3 cooking creators, 2 fitness creators, and 5 comedy creators."

**Context:** Adds per-creator API cost. Only valuable after aggregate_creators (5.3) validates users care about creator-level insights.

**Effort:** M
**Priority:** P4
**Depends on:** aggregate_creators tool (5.3)

---

### Prompt Registry with Eval Contracts (9.5)

**What:** Formalize prompt versioning: `prompts/{name}/v1.0.md` + `eval_set.jsonl` + `threshold.yaml`. Every prompt change runs eval set. Regressions block deployment.

**Why:** Makes prompt changes safe and measurable. Prevents quality regressions.

**Context:** Builds on prompts.py (5.1) and eval dataset (8.4). The infrastructure that makes prompt engineering a science instead of art.

**Effort:** L
**Priority:** P4
**Depends on:** Eval dataset V1 (8.4)

---

### Open-Source Ontology Publication (9.6)

**What:** Publish ONTOLOGY.md and PHILOSOPHY.md as standalone content marketing assets.

**Why:** Brand building, community engagement, top-of-funnel. The ontology has been validated by real production usage at this point.

**Context:** Only valuable after ontology has been tested and refined in production.

**Effort:** S
**Priority:** P4
**Depends on:** Production-validated ontology

---

## Deferred Product

### Frontend UX Design

**What:** Proper design for entity cards, collection views, inline previews, conversation history sidebar.

**Why:** Current chat UI is functional but minimal. Product experience matters for retention.

**Effort:** XL
**Priority:** P2
**Depends on:** Launch + user feedback on what matters most

---

### Conversation Search / History UI

**What:** Browse old conversations, search across chat history.

**Why:** Users lose context across sessions. Basic usability gap.

**Effort:** M
**Priority:** P2
**Depends on:** None

---

### Stripe Billing Integration

**What:** Replace manual pricing with Stripe Checkout + subscription management.

**Why:** Manual pricing doesn't scale past 100 users.

**Effort:** L
**Priority:** P3
**Depends on:** Credit model calibration (8.5)

---

### Apple OAuth

**What:** Add Apple as OAuth provider alongside Google.

**Why:** Required for iOS users who prefer Apple sign-in. Google OAuth sufficient for MVP.

**Effort:** S
**Priority:** P3
**Depends on:** None

---

### Per-User Cost Dashboards

**What:** Expose cost tracking to users ("you've used X credits this month, Y remaining").

**Why:** Transparency builds trust. Users want to understand their usage.

**Effort:** M
**Priority:** P3
**Depends on:** Credit system (7.1-7.4)

---

### Collection Export (CSV, Notion, Google Sheets)

**What:** Export entity lists (books found, restaurants saved, etc.) to external tools.

**Why:** Users want to act on insights — add books to reading list, save restaurants to Maps.

**Effort:** M
**Priority:** P3
**Depends on:** Entity resolution working well

---

### TikTok Data Portability API (EEA/UK)

**What:** OAuth-based ingestion for European users via TikTok's Data Portability API. Minutes vs days for data access.

**Why:** EU/UK users have legal right to data portability. Much better UX than ZIP export.

**Effort:** M
**Priority:** P3
**Depends on:** None

---

### Wrapped-Style Shareable Graphics

**What:** Visual summary cards (like Spotify Wrapped) that users can share on social media.

**Why:** Viral hook. Users share → new users discover Attic.

**Effort:** L
**Priority:** P4
**Depends on:** Cross-item pattern analysis (9.2)

---

### Continuous Ingestion (Share Sheet)

**What:** iOS shortcut / share extension to send individual TikToks to Attic in real-time.

**Why:** Makes subscription sticky — Attic stays current, not just a one-time analysis.

**Effort:** XL
**Priority:** P4
**Depends on:** After 100 paying users validate core product

---

### Multi-Platform Support (Instagram, YouTube)

**What:** Adapter architecture for Instagram Reels, YouTube Shorts exports.

**Why:** Expands addressable market. Adapter architecture already planned.

**Effort:** XL
**Priority:** P4
**Depends on:** TikTok validates first

---

### MCP Server Wrappers

**What:** Wrap entity resolution APIs in MCP protocol for interoperability.

**Why:** Ecosystem play — let other tools use Attic's entity resolution.

**Effort:** M
**Priority:** P4
**Depends on:** Direct wrappers stable in production

---

### Data Marketplace / Attic Collective

**What:** Anonymized aggregate insights across users. Trend data, cultural analytics.

**Why:** Potential B2B revenue stream.

**Context:** Legal questions unresolved. Do NOT build until legal green-light.

**Effort:** XL
**Priority:** P4
**Depends on:** Legal counsel

---

## Completed

- [x] **LocalStack Docker simplification** — removed Step Functions from docker-compose SERVICES list, updated health check expectations.
  **Completed:** Wave 1 (2026-03-14)
