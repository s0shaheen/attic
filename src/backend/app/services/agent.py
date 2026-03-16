"""Agent loop using manual Anthropic SDK tool calling.

Implements a ~50-line core loop that:
1. Sends user message + conversation history to Claude Haiku 4.5
2. If Claude returns tool_use blocks, dispatches to agent_tools
3. Feeds tool results back to Claude
4. Repeats until Claude returns a text response (or hits limits)
5. Yields SSE events as an async generator

Cost controls: 50 tool calls per query, 200 per hour per user.
"""

import json
import logging
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.services.agent_tools import (
    AgentToolResult,
    analyze_visual,
    classify,
    get_stats,
    get_tool_definitions,
    query_items,
    resolve_entity,
    search_similar,
)
from app.services.prompts import build_system_prompt

logger = logging.getLogger(__name__)

# Agent config
MODEL = "claude-haiku-4-5-20251001"

# Module-level Anthropic client for connection reuse
_anthropic_client: anthropic.AsyncAnthropic | None = None


def _get_anthropic_client() -> anthropic.AsyncAnthropic:
    """Get or create the shared Anthropic client.

    Reads API key from settings on first init. Cached for process lifetime.
    """
    global _anthropic_client
    if _anthropic_client is None:
        from app.config import get_settings

        _anthropic_client = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)
    return _anthropic_client


MAX_TOKENS = 4096
MAX_TOOL_CALLS_PER_QUERY = 50
MAX_TOOL_CALLS_PER_HOUR = 200

# ---------------------------------------------------------------------------
# Rate limiting (in-memory, per-process)
# ---------------------------------------------------------------------------

# user_id -> list of timestamps
_hourly_counts: dict[str, list[float]] = {}


def _check_hourly_limit(user_id: str) -> bool:
    """Check if user is within the hourly tool call limit."""
    now = time.time()
    cutoff = now - 3600

    timestamps = _hourly_counts.get(user_id, [])
    # Prune old entries
    timestamps = [t for t in timestamps if t > cutoff]
    _hourly_counts[user_id] = timestamps

    return len(timestamps) < MAX_TOOL_CALLS_PER_HOUR


def _record_tool_call(user_id: str) -> None:
    """Record a tool call for rate limiting."""
    if user_id not in _hourly_counts:
        _hourly_counts[user_id] = []
    _hourly_counts[user_id].append(time.time())


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------


_QUERY_ITEMS_KEYS = frozenset(
    {
        "search_text",
        "hashtag",
        "creator",
        "topic",
        "affect",
        "genre",
        "media_type",
        "limit",
        "offset",
    }
)


async def _dispatch_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    db: AsyncSession,
    settings: Settings,
    user_id: UUID,
) -> AgentToolResult:
    """Dispatch a tool call to the appropriate handler."""
    if tool_name == "query_items":
        filtered = {k: v for k, v in tool_input.items() if k in _QUERY_ITEMS_KEYS}
        return await query_items(db, user_id, **filtered)

    elif tool_name == "classify":
        return await classify(db, settings, UUID(tool_input["media_event_id"]), user_id)

    elif tool_name == "analyze_visual":
        return await analyze_visual(
            db,
            settings,
            UUID(tool_input["media_event_id"]),
            user_id,
            focus=tool_input.get("focus"),
        )

    elif tool_name == "resolve_entity":
        return await resolve_entity(
            db,
            settings,
            UUID(tool_input["media_event_id"]),
            user_id,
            tool_input["entity_type"],
            tool_input["entity_query"],
        )

    elif tool_name == "search_similar":
        return await search_similar(
            db,
            settings,
            user_id,
            query_text=tool_input["query_text"],
            limit=tool_input.get("limit", 10),
        )

    elif tool_name == "get_stats":
        return await get_stats(
            db,
            user_id,
            stat_type=tool_input["stat_type"],
            field=tool_input.get("field"),
        )

    else:
        return AgentToolResult(success=False, error=f"Unknown tool: {tool_name}")


# ---------------------------------------------------------------------------
# SSE event helpers
# ---------------------------------------------------------------------------


@dataclass
class SSEEvent:
    """Server-Sent Event."""

    event: str
    data: str


def _sse_token(text: str) -> SSEEvent:
    return SSEEvent(event="token", data=json.dumps({"text": text}))


def _sse_done(total_tokens: int | None = None) -> SSEEvent:
    return SSEEvent(event="done", data=json.dumps({"total_tokens": total_tokens}))


def _sse_error(message: str) -> SSEEvent:
    return SSEEvent(event="error", data=json.dumps({"error": message}))


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------


async def run_agent(
    user_message: str,
    conversation_history: list[dict[str, Any]],
    db: AsyncSession,
    settings: Settings,
    user_id: UUID,
) -> AsyncGenerator[SSEEvent, None]:
    """Run the agent loop, yielding SSE events.

    Args:
        user_message: The user's current message.
        conversation_history: Prior messages in Anthropic API format.
        db: Async database session.
        settings: Application settings.
        user_id: The authenticated user's ID.

    Yields:
        SSEEvent objects (token, done, or error).
    """
    user_id_str = str(user_id)

    # Check hourly rate limit
    if not _check_hourly_limit(user_id_str):
        yield _sse_error("You've reached the hourly tool usage limit. Please try again later.")
        yield _sse_done()
        return

    # Build messages
    messages = list(conversation_history)
    messages.append({"role": "user", "content": user_message})

    client = _get_anthropic_client()
    tool_calls_this_query = 0
    total_tokens = 0

    try:
        while True:
            # Call Claude
            response = await client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=build_system_prompt(),
                tools=get_tool_definitions(),
                messages=messages,
            )

            total_tokens += response.usage.input_tokens + response.usage.output_tokens

            # Process response blocks
            assistant_content = response.content
            has_tool_use = any(block.type == "tool_use" for block in assistant_content)

            # Yield any text blocks
            for block in assistant_content:
                if block.type == "text" and block.text:
                    yield _sse_token(block.text)

            # If no tool use, we're done
            if not has_tool_use:
                break

            # Process tool calls
            tool_results = []
            for block in assistant_content:
                if block.type != "tool_use":
                    continue

                tool_calls_this_query += 1

                # Per-query limit
                if tool_calls_this_query > MAX_TOOL_CALLS_PER_QUERY:
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(
                                {"error": "Tool call limit reached for this query."}
                            ),
                            "is_error": True,
                        }
                    )
                    continue

                # Hourly limit
                if not _check_hourly_limit(user_id_str):
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps({"error": "Hourly tool call limit reached."}),
                            "is_error": True,
                        }
                    )
                    continue

                _record_tool_call(user_id_str)

                # Dispatch tool
                result = await _dispatch_tool(block.name, block.input, db, settings, user_id)

                # Format result for Claude
                if result.success:
                    content = json.dumps(result.data, default=str)
                else:
                    content = json.dumps({"error": result.error})

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": content,
                        "is_error": not result.success,
                    }
                )

            # Add assistant message and tool results to conversation
            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})

    except anthropic.APIError as e:
        logger.error({"event": "agent_api_error", "error": str(e), "user_id": user_id_str})
        yield _sse_error("I'm having trouble connecting right now. Please try again.")

    except Exception as e:
        logger.error({"event": "agent_loop_error", "error": str(e), "user_id": user_id_str})
        yield _sse_error("Something went wrong. Please try again.")

    yield _sse_done(total_tokens)
