"""Tests for HTTP-level rate limiting."""

import time
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.rate_limit import (
    _check_rate_limit,
    _chat_request_times,
    _record_request,
    _upload_request_times,
    check_chat_rate_limit,
    check_upload_rate_limit,
)
from app.models.auth import AuthenticatedUser


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


class TestCheckRateLimit:
    def setup_method(self):
        _chat_request_times.clear()
        _upload_request_times.clear()

    def test_allows_under_limit(self):
        assert _check_rate_limit(_chat_request_times, "user1", max_requests=5) is True

    def test_blocks_over_limit(self):
        now = time.time()
        _chat_request_times["user1"] = [now] * 5
        assert _check_rate_limit(_chat_request_times, "user1", max_requests=5) is False

    def test_prunes_expired_entries(self):
        old = time.time() - 120  # 2 minutes ago, outside 60s window
        _chat_request_times["user1"] = [old] * 100
        assert _check_rate_limit(_chat_request_times, "user1", max_requests=5) is True
        assert len(_chat_request_times["user1"]) == 0

    def test_record_request_creates_entry(self):
        _record_request(_chat_request_times, "user1")
        assert len(_chat_request_times["user1"]) == 1

    def test_record_request_appends(self):
        _record_request(_chat_request_times, "user1")
        _record_request(_chat_request_times, "user1")
        assert len(_chat_request_times["user1"]) == 2

    def test_separate_stores_for_chat_and_upload(self):
        """Chat and upload rate limits use independent counters."""
        now = time.time()
        _chat_request_times["user1"] = [now] * 20
        assert _check_rate_limit(_upload_request_times, "user1", max_requests=5) is True


# ---------------------------------------------------------------------------
# Dependency functions
# ---------------------------------------------------------------------------


class TestChatRateLimitDependency:
    def setup_method(self):
        _chat_request_times.clear()

    @pytest.mark.asyncio
    async def test_allows_request_under_limit(self):
        user = AuthenticatedUser(id=uuid4(), email="test@test.com")
        settings = MagicMock()
        settings.chat_rate_limit_per_minute = 20

        result = await check_chat_rate_limit(user=user, settings=settings)
        assert result.id == user.id

    @pytest.mark.asyncio
    async def test_blocks_request_over_limit(self):
        user = AuthenticatedUser(id=uuid4(), email="test@test.com")
        settings = MagicMock()
        settings.chat_rate_limit_per_minute = 2

        # Fill up the limit
        now = time.time()
        _chat_request_times[str(user.id)] = [now] * 2

        with pytest.raises(HTTPException) as exc_info:
            await check_chat_rate_limit(user=user, settings=settings)

        assert exc_info.value.status_code == 429
        assert "Too many requests" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_records_request_after_check(self):
        user = AuthenticatedUser(id=uuid4(), email="test@test.com")
        settings = MagicMock()
        settings.chat_rate_limit_per_minute = 20

        await check_chat_rate_limit(user=user, settings=settings)
        assert len(_chat_request_times[str(user.id)]) == 1


class TestUploadRateLimitDependency:
    def setup_method(self):
        _upload_request_times.clear()

    @pytest.mark.asyncio
    async def test_allows_request_under_limit(self):
        user = AuthenticatedUser(id=uuid4(), email="test@test.com")
        settings = MagicMock()
        settings.upload_rate_limit_per_minute = 5

        result = await check_upload_rate_limit(user=user, settings=settings)
        assert result.id == user.id

    @pytest.mark.asyncio
    async def test_blocks_request_over_limit(self):
        user = AuthenticatedUser(id=uuid4(), email="test@test.com")
        settings = MagicMock()
        settings.upload_rate_limit_per_minute = 2

        now = time.time()
        _upload_request_times[str(user.id)] = [now] * 2

        with pytest.raises(HTTPException) as exc_info:
            await check_upload_rate_limit(user=user, settings=settings)

        assert exc_info.value.status_code == 429
        assert "upload" in exc_info.value.detail.lower()
