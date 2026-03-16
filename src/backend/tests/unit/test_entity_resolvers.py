"""Tests for entity resolution API wrappers."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.entity_resolvers import (
    ENTITY_TYPE_MAP,
    EntityResolutionResult,
    _request_with_retry,
    resolve_book,
    resolve_entity,
    resolve_movie_or_tv,
    resolve_place,
)

# ---------------------------------------------------------------------------
# Google Maps (Places)
# ---------------------------------------------------------------------------


class TestResolvePlace:
    @pytest.mark.asyncio
    async def test_resolve_place_success(self):
        mock_response = httpx.Response(
            200,
            json={
                "places": [
                    {
                        "displayName": {"text": "Shake Shack"},
                        "formattedAddress": "123 Broadway, NY",
                        "types": ["restaurant"],
                        "rating": 4.5,
                        "googleMapsUri": "https://maps.google.com/...",
                    }
                ]
            },
        )
        with patch("app.services.entity_resolvers._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await resolve_place("test-key", "Shake Shack NYC")

        assert result.success is True
        assert result.entity.name == "Shake Shack"
        assert result.entity.entity_type == "place"
        assert result.entity.metadata["rating"] == 4.5

    @pytest.mark.asyncio
    async def test_resolve_place_no_results(self):
        mock_response = httpx.Response(200, json={"places": []})
        with patch("app.services.entity_resolvers._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await resolve_place("test-key", "nonexistent place")

        assert result.success is False
        assert "No places found" in result.error

    @pytest.mark.asyncio
    async def test_resolve_place_api_error(self):
        mock_response = httpx.Response(500, json={})
        with (
            patch("app.services.entity_resolvers._get_client") as mock_get_client,
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await resolve_place("test-key", "Shake Shack")

        assert result.success is False
        assert "500" in result.error

    @pytest.mark.asyncio
    async def test_resolve_place_timeout(self):
        with patch("app.services.entity_resolvers._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

            result = await resolve_place("test-key", "Shake Shack")

        assert result.success is False
        assert "timed out" in result.error


# ---------------------------------------------------------------------------
# Google Books
# ---------------------------------------------------------------------------


class TestResolveBook:
    @pytest.mark.asyncio
    async def test_resolve_book_success(self):
        mock_response = httpx.Response(
            200,
            json={
                "items": [
                    {
                        "volumeInfo": {
                            "title": "Atomic Habits",
                            "authors": ["James Clear"],
                            "publishedDate": "2018",
                            "description": "A book about habits.",
                            "categories": ["Self-Help"],
                        }
                    }
                ]
            },
        )
        with patch("app.services.entity_resolvers._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await resolve_book(None, "Atomic Habits")

        assert result.success is True
        assert result.entity.name == "Atomic Habits"
        assert result.entity.metadata["authors"] == ["James Clear"]

    @pytest.mark.asyncio
    async def test_resolve_book_no_results(self):
        mock_response = httpx.Response(200, json={"items": []})
        with patch("app.services.entity_resolvers._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await resolve_book(None, "nonexistent book")

        assert result.success is False

    @pytest.mark.asyncio
    async def test_resolve_book_with_api_key(self):
        mock_response = httpx.Response(200, json={"items": [{"volumeInfo": {"title": "Test"}}]})
        with patch("app.services.entity_resolvers._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await resolve_book("test-key", "Test Book")

        assert result.success is True


# ---------------------------------------------------------------------------
# TMDB
# ---------------------------------------------------------------------------


class TestResolveMovieOrTv:
    @pytest.mark.asyncio
    async def test_resolve_movie_success(self):
        mock_response = httpx.Response(
            200,
            json={
                "results": [
                    {
                        "media_type": "movie",
                        "title": "Inception",
                        "id": 27205,
                        "overview": "A thief who steals secrets...",
                        "release_date": "2010-07-16",
                        "vote_average": 8.4,
                        "poster_path": "/poster.jpg",
                    }
                ]
            },
        )
        with patch("app.services.entity_resolvers._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await resolve_movie_or_tv("test-key", "Inception")

        assert result.success is True
        assert result.entity.name == "Inception"
        assert result.entity.entity_type == "movie"
        assert result.entity.metadata["tmdb_id"] == 27205

    @pytest.mark.asyncio
    async def test_resolve_tv_success(self):
        mock_response = httpx.Response(
            200,
            json={
                "results": [
                    {
                        "media_type": "tv",
                        "name": "Breaking Bad",
                        "id": 1396,
                        "first_air_date": "2008-01-20",
                        "vote_average": 8.9,
                    }
                ]
            },
        )
        with patch("app.services.entity_resolvers._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await resolve_movie_or_tv("test-key", "Breaking Bad")

        assert result.success is True
        assert result.entity.entity_type == "tv"

    @pytest.mark.asyncio
    async def test_resolve_movie_filters_non_media(self):
        mock_response = httpx.Response(
            200,
            json={
                "results": [
                    {"media_type": "person", "name": "Christopher Nolan"},
                ]
            },
        )
        with patch("app.services.entity_resolvers._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await resolve_movie_or_tv("test-key", "Christopher Nolan")

        assert result.success is False


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


class TestResolveEntityDispatcher:
    def test_entity_type_map_covers_all_types(self):
        expected_types = {
            "place",
            "restaurant",
            "location",
            "book",
            "movie",
            "tv",
            "tv_show",
            "show",
            "music",
            "song",
            "artist",
        }
        assert set(ENTITY_TYPE_MAP.keys()) == expected_types

    @pytest.mark.asyncio
    async def test_unknown_entity_type_returns_error(self):
        result = await resolve_entity(
            entity_type="unknown_type",
            query="test",
            google_maps_api_key="k",
            google_books_api_key=None,
            tmdb_api_key="k",
            spotify_client_id="k",
            spotify_client_secret="k",
        )
        assert result.success is False
        assert "Unknown entity type" in result.error

    @pytest.mark.asyncio
    async def test_dispatcher_routes_place(self):
        with patch("app.services.entity_resolvers.resolve_place", new_callable=AsyncMock) as mock:
            mock.return_value = EntityResolutionResult(success=True)
            await resolve_entity(
                entity_type="restaurant",
                query="test",
                google_maps_api_key="k",
                google_books_api_key=None,
                tmdb_api_key="k",
                spotify_client_id="k",
                spotify_client_secret="k",
            )
            mock.assert_called_once_with("k", "test")

    @pytest.mark.asyncio
    async def test_dispatcher_routes_book(self):
        with patch("app.services.entity_resolvers.resolve_book", new_callable=AsyncMock) as mock:
            mock.return_value = EntityResolutionResult(success=True)
            await resolve_entity(
                entity_type="book",
                query="test",
                google_maps_api_key="k",
                google_books_api_key="bk",
                tmdb_api_key="k",
                spotify_client_id="k",
                spotify_client_secret="k",
            )
            mock.assert_called_once_with("bk", "test")


# ---------------------------------------------------------------------------
# _request_with_retry()
# ---------------------------------------------------------------------------


class TestRequestWithRetry:
    @pytest.mark.asyncio
    async def test_request_with_retry_429_with_retry_after_succeeds(self):
        """T1: 429 with Retry-After header -> waits -> retries -> 200."""
        resp_429 = httpx.Response(
            429,
            headers={"Retry-After": "1"},
            json={},
        )
        resp_200 = httpx.Response(200, json={"ok": True})

        with (
            patch("app.services.entity_resolvers._get_client") as mock_get_client,
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.get = AsyncMock(side_effect=[resp_429, resp_200])

            result = await _request_with_retry("get", "https://example.com/api")

        assert result.status_code == 200
        mock_sleep.assert_called_once_with(1.0)

    @pytest.mark.asyncio
    async def test_request_with_retry_429_exponential_backoff(self):
        """T2: 429 without Retry-After -> uses backoff schedule (1s first)."""
        resp_429 = httpx.Response(429, json={})
        resp_200 = httpx.Response(200, json={"ok": True})

        with (
            patch("app.services.entity_resolvers._get_client") as mock_get_client,
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.get = AsyncMock(side_effect=[resp_429, resp_200])

            result = await _request_with_retry("get", "https://example.com/api")

        assert result.status_code == 200
        mock_sleep.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_request_with_retry_5xx_exhausted_returns_last_response(self):
        """T3: All 4 attempts return 503 -> returns last 503 response."""
        resp_503 = httpx.Response(503, json={})

        with (
            patch("app.services.entity_resolvers._get_client") as mock_get_client,
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.get = AsyncMock(return_value=resp_503)

            result = await _request_with_retry("get", "https://example.com/api")

        assert result.status_code == 503
        assert mock_sleep.call_count == 3
        assert mock_client.get.call_count == 4  # initial + 3 retries

    @pytest.mark.asyncio
    async def test_request_with_retry_200_no_retry(self):
        """T4: 200 on first try -> returns immediately, no sleep."""
        resp_200 = httpx.Response(200, json={"ok": True})

        with (
            patch("app.services.entity_resolvers._get_client") as mock_get_client,
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.get = AsyncMock(return_value=resp_200)

            result = await _request_with_retry("get", "https://example.com/api")

        assert result.status_code == 200
        mock_sleep.assert_not_called()
        mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_with_retry_retry_after_capped_at_30s(self):
        """T5: Retry-After: 120 -> capped to 30s."""
        resp_429 = httpx.Response(
            429,
            headers={"Retry-After": "120"},
            json={},
        )
        resp_200 = httpx.Response(200, json={"ok": True})

        # start=0.0, elapsed check after first attempt: monotonic returns 0.0
        # so elapsed=0, wait=30, elapsed+wait=30 which is NOT > 30 -> proceed
        with (
            patch("app.services.entity_resolvers._get_client") as mock_get_client,
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("time.monotonic", side_effect=[0.0, 0.0]),
        ):
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.get = AsyncMock(side_effect=[resp_429, resp_200])

            result = await _request_with_retry("get", "https://example.com/api")

        assert result.status_code == 200
        mock_sleep.assert_called_once_with(30)

    @pytest.mark.asyncio
    async def test_resolver_uses_request_with_retry(self):
        """T6: resolve_place calls _request_with_retry with correct args."""
        mock_response = httpx.Response(
            200,
            json={
                "places": [
                    {
                        "displayName": {"text": "Shake Shack"},
                        "formattedAddress": "123 Broadway, NY",
                        "types": ["restaurant"],
                        "rating": 4.5,
                        "googleMapsUri": "https://maps.google.com/...",
                    }
                ]
            },
        )
        with patch(
            "app.services.entity_resolvers._request_with_retry",
            new_callable=AsyncMock,
        ) as mock_retry:
            mock_retry.return_value = mock_response

            result = await resolve_place("test-key", "Shake Shack NYC")

        assert result.success is True
        mock_retry.assert_called_once()
        call_args = mock_retry.call_args
        assert call_args[0][0] == "post"
        assert "places.googleapis.com" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_request_with_retry_total_timeout_cap(self):
        """T6b: Elapsed time > 30s -> stops retrying early."""
        resp_503 = httpx.Response(503, json={})

        # Simulate: start=0, after first request elapsed=25s, wait=4s would exceed 30s
        # So we need: monotonic returns 0 (start), then 25.0 (after first attempt)
        # wait would be _BACKOFF_SCHEDULE[0]=1, elapsed+wait=26 < 30 -> retry
        # Then monotonic returns 28.0, wait=2, elapsed+wait=30 -> stops
        # Actually let me make it simpler: start at 0, after first call returns 29,
        # wait=1s, elapsed+wait=30 -> 30 > 30 is False (not >), actually >=30 not > 30
        # The check is: if elapsed + wait > _TOTAL_RETRY_TIMEOUT: return resp
        # So 29 + 1 = 30, which is NOT > 30, so it would continue.
        # Let's use: start=0, after first call=29.1, wait=1 -> 30.1 > 30 -> stop
        with (
            patch("app.services.entity_resolvers._get_client") as mock_get_client,
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("time.monotonic", side_effect=[0.0, 29.1]),
        ):
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.get = AsyncMock(return_value=resp_503)

            result = await _request_with_retry("get", "https://example.com/api")

        assert result.status_code == 503
        # Should NOT have slept -- total timeout exceeded before first retry
        mock_sleep.assert_not_called()
        # Only 1 HTTP call made (initial attempt, then timeout check stops it)
        mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_with_retry_invalid_retry_after_uses_backoff(self):
        """T7: Non-numeric Retry-After header falls back to backoff schedule."""
        resp_429 = httpx.Response(
            429,
            headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"},
            json={},
        )
        resp_200 = httpx.Response(200, json={"ok": True})

        with (
            patch("app.services.entity_resolvers._get_client") as mock_get_client,
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.get = AsyncMock(side_effect=[resp_429, resp_200])

            result = await _request_with_retry("get", "https://example.com/api")

        assert result.status_code == 200
        # Falls back to _BACKOFF_SCHEDULE[0] = 1
        mock_sleep.assert_called_once_with(1)
