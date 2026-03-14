# Attic — TODOs

## Deferred Engineering

- [ ] **Entity API rate limit handling** — resolve_entity tools have no rate-limit detection or backoff. Add try/except with exponential backoff + return error result. Critical gap (silent failure today).
- [ ] **DB upsert constraint violation test** — cache write-back should log-and-continue on constraint errors. No test coverage yet.
- [ ] **Conversation not found → 404** — chat endpoint should return 404 for stale/invalid conversation IDs. No handler yet.
- [ ] **SSE reconnection / stream drop handling** — frontend should handle SSE stream drops gracefully (auto-retry or "connection lost" UI).
- [ ] **Prompt caching verification** — verify Claude prompt caching is working (ontology prefix is cache-hit across users). Check Anthropic dashboard metrics after launch.
- [ ] **Split agent_tools.py if >500 lines** — currently single file, split by tool type if it grows.
- [ ] **Extract shared package (attic_core/)** — if Lambda/backend code sharing gets messy, extract models+parser into a shared package. Deferred at MVP.
- [ ] **LocalStack Docker simplification** — remove Step Functions from docker-compose SERVICES list, update health check expectations.

## Deferred Product

- [ ] **Frontend UX design** — current minimal chat UI is functional only. Need proper design for entity cards, collection views, inline previews, Wrapped-style reveal.
- [ ] **Wrapped-style shareable graphics** — viral hook. Requires design + share flow. Post core-chat-validates.
- [ ] **Continuous ingestion (share sheet)** — iOS shortcut / share extension to send individual TikToks. Makes subscription sticky. Post-PMF.
- [ ] **Multi-platform support (Instagram, YouTube)** — adapter architecture ready, validate TikTok first.
- [ ] **Stripe Billing integration** — manual pricing for first 100 users, then integrate Stripe.
- [ ] **Apple OAuth** — Google OAuth sufficient for MVP.
- [ ] **Open-source ontology repo** — publish taxonomy + production usage data after ontology validates in production.
- [ ] **MCP server wrappers** — wrap entity resolution APIs in MCP protocol for interop. Direct wrappers sufficient at MVP.
- [ ] **Data marketplace / Attic Collective** — legal questions unresolved. Do NOT build until legal green-light.
- [ ] **Batch vision pre-processing** — text-first is sufficient. On-demand agent vision covers gaps.
- [ ] **Per-user cost dashboards** — expose cost tracking to users ("you've used $X this month"). Post-launch.
- [ ] **Conversation search / history UI** — browse old conversations, search across chat history.
- [ ] **Collection export (CSV, Notion, Google Sheets)** — export entity lists to external tools.
- [ ] **TikTok Data Portability API (EEA/UK)** — OAuth-based ingestion for European users. Minutes vs days for data access.
