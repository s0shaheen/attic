"""In-memory per-user rate limiting.

Sliding-window counters keyed by user_id. Per-process only — limits are
approximate when running multiple workers, which is fine for <20 alpha users.

Two layers:
1. HTTP-level: throttles requests to endpoints (e.g., 20 chat req/min).
2. Agent-level: throttles tool calls within the agent loop (existing logic
   in agent.py, now configured via Settings).
"""

import time

from fastapi import Depends, HTTPException

from app.config import Settings, get_settings
from app.core.auth import get_current_user
from app.models.auth import AuthenticatedUser

# user_id -> list of request timestamps
_chat_request_times: dict[str, list[float]] = {}
_upload_request_times: dict[str, list[float]] = {}


def reset_rate_limit_state() -> None:
    """Clear HTTP-layer rate limit state. For use in test teardown.

    Note: agent-level rate limits (_hourly_counts in agent.py) are separate
    and must be cleared independently.
    """
    _chat_request_times.clear()
    _upload_request_times.clear()


def _check_rate_limit(
    store: dict[str, list[float]],
    user_id: str,
    max_requests: int,
    window_seconds: int = 60,
) -> bool:
    """Check if a user is within the rate limit for a given window.

    Prunes expired entries and returns True if under the limit.
    """
    now = time.time()
    cutoff = now - window_seconds

    timestamps = store.get(user_id, [])
    timestamps = [t for t in timestamps if t > cutoff]
    store[user_id] = timestamps

    return len(timestamps) < max_requests


def _record_request(store: dict[str, list[float]], user_id: str) -> None:
    """Record a request timestamp."""
    if user_id not in store:
        store[user_id] = []
    store[user_id].append(time.time())


async def check_chat_rate_limit(
    user: AuthenticatedUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    """FastAPI dependency that enforces per-user chat rate limits.

    Returns the authenticated user if within limits, raises 429 otherwise.
    """
    user_id_str = str(user.id)

    if not _check_rate_limit(
        _chat_request_times,
        user_id_str,
        settings.chat_rate_limit_per_minute,
    ):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a moment before sending another message.",
        )

    _record_request(_chat_request_times, user_id_str)
    return user


async def check_upload_rate_limit(
    user: AuthenticatedUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    """FastAPI dependency that enforces per-user upload rate limits.

    Returns the authenticated user if within limits, raises 429 otherwise.
    """
    user_id_str = str(user.id)

    if not _check_rate_limit(
        _upload_request_times,
        user_id_str,
        settings.upload_rate_limit_per_minute,
    ):
        raise HTTPException(
            status_code=429,
            detail="Too many upload requests. Please wait before trying again.",
        )

    _record_request(_upload_request_times, user_id_str)
    return user
