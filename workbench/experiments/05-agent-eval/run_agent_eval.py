#!/usr/bin/env python
"""Run evaluation queries against the production agent and capture results.

Sends test queries through the agent loop (bypassing HTTP), captures tool calls,
structured SSE events, and text responses. Saves per-query results for analysis.

Usage:
    python workbench/experiments/05-agent-eval/run_agent_eval.py
    python workbench/experiments/05-agent-eval/run_agent_eval.py --limit 5
    python workbench/experiments/05-agent-eval/run_agent_eval.py --query "show me fitness videos"
    python workbench/experiments/05-agent-eval/run_agent_eval.py --verbose

Requires: Database seeded with test data (run seed_from_apify.py first)
"""

import asyncio
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
RESULTS_DIR = SCRIPT_DIR / "results"
sys.path.insert(0, str(REPO_ROOT / "src" / "backend"))

from dotenv import load_dotenv

load_dotenv(REPO_ROOT / "src" / "backend" / ".env")

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.services.agent import SSEEvent, run_agent

# Test user (must match seed_from_apify.py)
TEST_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
TEST_EMAIL = "test@attic.to"

# ── Test Queries ──────────────────────────────────────────────────────────
# Each query has:
#   - query: the user message
#   - strategy: which query plan template it should use
#   - expect_tools: tools the agent should call
#   - expect_results: what we expect in the response (for manual review)
#   - tags: for filtering

EVAL_QUERIES = [
    # === Simple Filter ===
    {
        "id": "filter-food",
        "query": "show me my food videos",
        "strategy": "simple_filter",
        "expect_tools": ["query_items"],
        "expect_results": "Should return items with topic=food",
        "tags": ["filter", "topic"],
    },
    {
        "id": "filter-fitness",
        "query": "any fitness or workout content?",
        "strategy": "simple_filter",
        "expect_tools": ["query_items"],
        "expect_results": "Should filter by topic=fitness or genre=workout",
        "tags": ["filter", "topic"],
    },
    {
        "id": "filter-creator",
        "query": "what have I saved from @realbrosofsimivalley1?",
        "strategy": "simple_filter",
        "expect_tools": ["query_items"],
        "expect_results": "Should filter by creator username",
        "tags": ["filter", "creator"],
    },
    {
        "id": "filter-funny",
        "query": "show me funny videos",
        "strategy": "simple_filter",
        "expect_tools": ["query_items"],
        "expect_results": "Should filter by affect=funny",
        "tags": ["filter", "affect"],
    },
    # === Broad / Overview ===
    {
        "id": "overview-feed",
        "query": "what kind of stuff do I save?",
        "strategy": "ambiguous_broad",
        "expect_tools": ["get_stats"],
        "expect_results": "Should give overview with topic/affect breakdown",
        "tags": ["overview", "stats"],
    },
    {
        "id": "overview-creators",
        "query": "who are my top creators?",
        "strategy": "creator_aggregation",
        "expect_tools": ["get_stats"],
        "expect_results": "Should return top creators with counts",
        "tags": ["overview", "creators"],
    },
    # === Interpretive / Vibe ===
    {
        "id": "vibe-relaxing",
        "query": "find me something chill and relaxing",
        "strategy": "interpretive_vibe",
        "expect_tools": ["search_similar"],
        "expect_results": "Should use semantic search for vibe match",
        "tags": ["vibe", "semantic"],
    },
    {
        "id": "vibe-learn",
        "query": "videos where I can learn something useful",
        "strategy": "interpretive_vibe",
        "expect_tools": ["search_similar"],
        "expect_results": "Should find informative/educational content",
        "tags": ["vibe", "semantic"],
    },
    # === Entity Retrieval ===
    {
        "id": "entity-books",
        "query": "have I saved any book recommendations?",
        "strategy": "entity_retrieval",
        "expect_tools": ["query_items"],
        "expect_results": "Should search for book-related content",
        "tags": ["entity", "books"],
    },
    {
        "id": "entity-restaurants",
        "query": "any restaurant or food place recommendations?",
        "strategy": "entity_retrieval",
        "expect_tools": ["query_items"],
        "expect_results": "Should find place/restaurant entities",
        "tags": ["entity", "places"],
    },
    # === Multi-step ===
    {
        "id": "multi-classify",
        "query": "pick a random video and tell me everything about it",
        "strategy": "multi_step",
        "expect_tools": ["query_items"],
        "expect_results": "Should pick an item and describe it richly",
        "tags": ["multi", "detail"],
    },
    {
        "id": "multi-compare",
        "query": "compare my food content vs fitness content",
        "strategy": "multi_step",
        "expect_tools": ["get_stats", "query_items"],
        "expect_results": "Should get stats for both and compare",
        "tags": ["multi", "compare"],
    },
]


async def run_single_query(
    query_spec: dict,
    db: AsyncSession,
    settings: Settings,
    user_id: UUID,
    verbose: bool = False,
) -> dict:
    """Run a single eval query and capture all events."""
    query = query_spec["query"]
    start = time.time()

    # Capture all events
    events: list[dict] = []
    text_chunks: list[str] = []
    tool_calls: list[dict] = []
    structured_events: list[dict] = []
    error = None

    try:
        async for sse_event in run_agent(
            user_message=query,
            conversation_history=[],
            db=db,
            settings=settings,
            user_id=user_id,
        ):
            event_data = json.loads(sse_event.data)
            events.append({"event": sse_event.event, "data": event_data})

            if sse_event.event == "token":
                text_chunks.append(event_data.get("text", ""))
            elif sse_event.event == "error":
                error = event_data.get("error", "Unknown error")
            elif sse_event.event == "tool_activity":
                tool_calls.append(event_data)
            elif sse_event.event in ("media_grid", "entity_card", "stat_card"):
                structured_events.append({
                    "type": sse_event.event,
                    "data": event_data,
                })
    except Exception as e:
        error = str(e)

    elapsed_ms = int((time.time() - start) * 1000)
    full_response = "".join(text_chunks)

    # Extract tool call sequence
    tool_sequence = [
        tc["tool_name"]
        for tc in tool_calls
        if tc.get("status") == "started"
    ]

    # Check expected tools
    expected = set(query_spec.get("expect_tools", []))
    actual = set(tool_sequence)
    tools_match = expected.issubset(actual)

    # Count tokens from done event
    done_events = [e for e in events if e["event"] == "done"]
    total_tokens = done_events[0]["data"].get("total_tokens") if done_events else None

    result = {
        "id": query_spec["id"],
        "query": query,
        "strategy": query_spec["strategy"],
        "tags": query_spec["tags"],
        "elapsed_ms": elapsed_ms,
        "total_tokens": total_tokens,
        "response_length": len(full_response),
        "response_text": full_response,
        "tool_sequence": tool_sequence,
        "tool_calls_count": len(tool_sequence),
        "expected_tools": list(expected),
        "tools_match": tools_match,
        "structured_events": structured_events,
        "structured_event_count": len(structured_events),
        "error": error,
        "success": error is None and len(full_response) > 0,
    }

    if verbose:
        status = "OK" if result["success"] else "FAIL"
        tools_status = "MATCH" if tools_match else f"MISMATCH (got {tool_sequence})"
        print(f"  [{status}] {query_spec['id']}: {elapsed_ms}ms, "
              f"{len(tool_sequence)} tools ({tools_status}), "
              f"{len(full_response)} chars, "
              f"{len(structured_events)} structured events")
        if error:
            print(f"    ERROR: {error}")

    return result


async def main() -> None:
    # Parse args
    limit = None
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    single_query = None
    for i, arg in enumerate(sys.argv):
        if arg == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
        if arg == "--query" and i + 1 < len(sys.argv):
            single_query = sys.argv[i + 1]

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_key:
        print("ERROR: ANTHROPIC_API_KEY not set (needed for Claude agent)")
        sys.exit(1)

    # Build settings
    settings = Settings(
        database_url=database_url,
        supabase_url=os.environ.get("SUPABASE_URL", ""),
        supabase_secret_key=os.environ.get("SUPABASE_SECRET_KEY", ""),
        supabase_jwt_secret=os.environ.get("SUPABASE_JWT_SECRET", ""),
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", ""),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
        anthropic_api_key=anthropic_key,
        gemini_api_key=os.environ.get("GEMINI_API_KEY"),
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
    )

    # Connect to DB
    connect_args = {}
    if "pooler.supabase.com" in database_url or ":6543/" in database_url:
        connect_args["statement_cache_size"] = 0

    engine = create_async_engine(database_url, echo=False, connect_args=connect_args)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Resolve test user ID from DB
    from sqlalchemy import select

    from app.models.user import User

    async with async_session() as session:
        result = await session.execute(select(User).where(User.email == TEST_EMAIL))
        user = result.scalar_one_or_none()
        if not user:
            print(f"ERROR: Test user {TEST_EMAIL} not found. Run seed_from_apify.py first.")
            sys.exit(1)
        user_id = user.id
        print(f"Test user: {user_id}")

    # Build query list
    if single_query:
        queries = [{
            "id": "adhoc",
            "query": single_query,
            "strategy": "adhoc",
            "expect_tools": [],
            "expect_results": "",
            "tags": ["adhoc"],
        }]
    else:
        queries = EVAL_QUERIES
        if limit:
            queries = queries[:limit]

    print(f"\nRunning {len(queries)} eval queries against agent...\n")

    # Run all queries
    all_results = []
    for i, query_spec in enumerate(queries):
        print(f"[{i + 1}/{len(queries)}] {query_spec['query'][:60]}...")
        async with async_session() as session:
            result = await run_single_query(query_spec, session, settings, user_id, verbose)
            all_results.append(result)

    # Save results
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    output_path = RESULTS_DIR / f"eval_{timestamp}.json"

    # Summary stats
    total = len(all_results)
    success = sum(1 for r in all_results if r["success"])
    tools_match = sum(1 for r in all_results if r["tools_match"])
    avg_latency = sum(r["elapsed_ms"] for r in all_results) / total if total else 0
    total_tokens = sum(r["total_tokens"] or 0 for r in all_results)
    structured_count = sum(r["structured_event_count"] for r in all_results)

    summary = {
        "timestamp": timestamp,
        "total_queries": total,
        "success_rate": f"{success}/{total} ({100 * success / total:.0f}%)" if total else "0/0",
        "tools_match_rate": f"{tools_match}/{total} ({100 * tools_match / total:.0f}%)" if total else "0/0",
        "avg_latency_ms": round(avg_latency),
        "total_tokens": total_tokens,
        "total_structured_events": structured_count,
    }

    output = {"summary": summary, "results": all_results}
    output_path.write_text(json.dumps(output, indent=2, default=str))

    # Print summary
    print(f"\n{'=' * 60}")
    print(f"AGENT EVAL RESULTS")
    print(f"{'=' * 60}")
    print(f"  Queries:          {total}")
    print(f"  Success:          {summary['success_rate']}")
    print(f"  Tools match:      {summary['tools_match_rate']}")
    print(f"  Avg latency:      {avg_latency:.0f}ms")
    print(f"  Total tokens:     {total_tokens:,}")
    print(f"  Structured events: {structured_count}")
    print(f"  Results saved:    {output_path}")

    # Per-query table
    print(f"\n{'ID':<20} {'ms':>6} {'Tools':>6} {'Match':>6} {'Events':>7} {'Status':>7}")
    print("-" * 60)
    for r in all_results:
        status = "OK" if r["success"] else "FAIL"
        match = "Y" if r["tools_match"] else "N"
        print(f"{r['id']:<20} {r['elapsed_ms']:>6} {r['tool_calls_count']:>6} "
              f"{match:>6} {r['structured_event_count']:>7} {status:>7}")

    # Print failures
    failures = [r for r in all_results if not r["success"]]
    if failures:
        print(f"\nFAILURES ({len(failures)}):")
        for r in failures:
            print(f"  {r['id']}: {r['error']}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
