"""Tests for entity resolution API wrappers."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.entity_resolvers import (
    ENTITY_TYPE_MAP,
    EntityResolutionResult,
    resolve_book,
    resolve_entity,
    resolve_movie_or_tv,
    resolve_music,
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
        with patch("app.services.entity_resolvers.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.post = AsyncMock(return_value=mock_response)

            result = await resolve_place("test-key", "Shake Shack NYC")

        assert result.success is True
        assert result.entity.name == "Shake Shack"
        assert result.entity.entity_type == "place"
        assert result.entity.metadata["rating"] == 4.5

    @pytest.mark.asyncio
    async def test_resolve_place_no_results(self):
        mock_response = httpx.Response(200, json={"places": []})
        with patch("app.services.entity_resolvers.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.post = AsyncMock(return_value=mock_response)

            result = await resolve_place("test-key", "nonexistent place")

        assert result.success is False
        assert "No places found" in result.error

    @pytest.mark.asyncio
    async def test_resolve_place_api_error(self):
        mock_response = httpx.Response(500, json={})
        with patch("app.services.entity_resolvers.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.post = AsyncMock(return_value=mock_response)

            result = await resolve_place("test-key", "Shake Shack")

        assert result.success is False
        assert "500" in result.error

    @pytest.mark.asyncio
    async def test_resolve_place_timeout(self):
        with patch("app.services.entity_resolvers.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

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
        with patch("app.services.entity_resolvers.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

            result = await resolve_book(None, "Atomic Habits")

        assert result.success is True
        assert result.entity.name == "Atomic Habits"
        assert result.entity.metadata["authors"] == ["James Clear"]

    @pytest.mark.asyncio
    async def test_resolve_book_no_results(self):
        mock_response = httpx.Response(200, json={"items": []})
        with patch("app.services.entity_resolvers.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

            result = await resolve_book(None, "nonexistent book")

        assert result.success is False

    @pytest.mark.asyncio
    async def test_resolve_book_with_api_key(self):
        mock_response = httpx.Response(200, json={"items": [{"volumeInfo": {"title": "Test"}}]})
        with patch("app.services.entity_resolvers.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

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
        with patch("app.services.entity_resolvers.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

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
        with patch("app.services.entity_resolvers.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

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
        with patch("app.services.entity_resolvers.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

            result = await resolve_movie_or_tv("test-key", "Christopher Nolan")

        assert result.success is False


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


class TestResolveEntityDispatcher:
    def test_entity_type_map_covers_all_types(self):
        expected_types = {
            "place", "restaurant", "location",
            "book",
            "movie", "tv", "tv_show", "show",
            "music", "song", "artist",
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
