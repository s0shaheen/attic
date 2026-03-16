# Attic — Architecture Reference

**Architecture:** Hybrid Agentic (minimal pre-processing + agent chat layer)
**Completed:** Waves 1-4 (Cleanup, Agent Backend, Pipeline, Frontend + Tests)
**Task Tracking:** [GitHub Project Board](https://github.com/users/s0shaheen/projects/2)

---

## Quick Reference

```
LLM Stack:
  Claude Haiku 4.5     — orchestrator (tool calling, prompt-cached ontology)
  Gemini 3 Flash       — classification + vision + Google Search grounding
  OpenAI embed-3-small — embeddings for semantic search
  Direct API wrappers  — entity resolution (Maps, Books, TMDB, Spotify)

Pipeline: SQS → single Lambda (parse → apify → subtitle → embed)
Agent:    FastAPI SSE streaming, manual Anthropic SDK tool loop
Frontend: Minimal chat UI (rebuild from scratch)
```

---

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent hosting | Inline SSE streaming | Simple, no new infra, partial responses useful |
| Agent SDK | Manual Anthropic SDK tool loop | Full control, explicit, ~50 lines |
| Multi-model | Direct Gemini 3 Flash API in tool funcs | One model for classify + vision + grounding |
| Entity resolution | Async Python functions (not MCP) | Direct API calls, wrap in MCP later if needed |
| Chat history | DB tables (conversations + messages) | Queryable, persistent, matches existing patterns |
| Cache write-back | Inline during tool execution | Upserts before returning, survives stream drops |
| Pipeline orchestration | SQS + single Lambda | Replaces Step Functions, simple for 4 linear steps |
| Ontology storage | Python dict in ontology.py | No YAML/DB, type-safe, testable |
| Error handling | Result objects (never raise) | Matches existing Result pattern, agent explains |
| SSE format | Minimal (token + done) | No tool-status events at MVP |
| Classification storage | JSONB + GIN index on media_events | Fast containment queries, no joins |
| Embedding timing | 4th pipeline step | Semantic search works from first chat |
| Frontend | Full rebuild | Current UI not desired |

---

## Key File Paths

```
src/backend/app/core/auth.py              # JWT validation
src/backend/app/services/uploads.py       # Upload service
src/backend/app/services/tiktok_parser.py # ZIP parser (634 lines)
src/backend/app/services/agent.py         # Agent loop
src/backend/app/services/agent_tools.py   # Tool functions
src/backend/app/services/gemini.py        # Gemini client
src/backend/app/services/ontology.py      # Ontology dict
src/backend/app/services/prompts.py       # System prompt builder
src/backend/app/services/entity_resolvers.py  # Entity API wrappers
src/backend/app/routers/chat.py           # Chat endpoint
src/lambdas/pipeline/handler.py           # Unified pipeline
src/frontend/                             # Next.js app
```
