"""Entity resolution via direct API wrappers.

Each resolver takes a surface-form string (e.g., "Atomic Habits", "Shake Shack")
and returns structured entity data. All return Result-style dataclasses (never raise).

Supported entity types:
- place → Google Maps Places API
- book → Google Books API
- movie/tv → TMDB API
- music → Spotify Web API
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10.0

# Retry configuration for transient HTTP errors
_RETRYABLE_STATUSES = {429, 500, 502, 503}
_MAX_RETRIES = 3
_BACKOFF_SCHEDULE = [1, 2, 4]  # seconds
_MAX_RETRY_AFTER = 30  # cap Retry-After header
_TOTAL_RETRY_TIMEOUT = 30  # seconds total across all retries

# Module-level client for connection reuse across calls
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Get or create the shared httpx client."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
    return _client


async def _request_with_retry(
    method: str,
    url: str,
    **kwargs: Any,
) -> httpx.Response:
    """HTTP request with retry on 429 + 5xx. Respects Retry-After header."""
    client = _get_client()
    start = time.monotonic()

    for attempt in range(_MAX_RETRIES + 1):
        http_method = getattr(client, method)
        resp = await http_method(url, **kwargs)

        if resp.status_code not in _RETRYABLE_STATUSES:
            return resp

        if attempt == _MAX_RETRIES:
            return resp  # exhausted retries, return last response

        # Calculate wait time
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                wait = min(float(retry_after), _MAX_RETRY_AFTER)
            except ValueError:
                wait = _BACKOFF_SCHEDULE[attempt]
        else:
            wait = _BACKOFF_SCHEDULE[attempt]

        # Check total time cap
        elapsed = time.monotonic() - start
        if elapsed + wait > _TOTAL_RETRY_TIMEOUT:
            return resp

        logger.warning(
            {
                "event": "http_retry",
                "url": url,
                "status": resp.status_code,
                "attempt": attempt + 1,
                "wait_seconds": wait,
            }
        )
        await asyncio.sleep(wait)

    return resp  # unreachable but satisfies type checker


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class ResolvedEntity:
    """A successfully resolved entity."""

    entity_type: str
    surface: str
    name: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EntityResolutionResult:
    """Result of an entity resolution attempt."""

    success: bool
    entity: ResolvedEntity | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Google Maps (Places)
# ---------------------------------------------------------------------------


async def resolve_place(
    api_key: str,
    query: str,
) -> EntityResolutionResult:
    """Resolve a place name using Google Maps Places API (Text Search).

    Args:
        api_key: Google Maps API key.
        query: Place name to search for (e.g., "Shake Shack NYC").

    Returns:
        EntityResolutionResult with place data or error.
    """
    try:
        resp = await _request_with_retry(
            "post",
            "https://places.googleapis.com/v1/places:searchText",
            headers={
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": (
                    "places.displayName,places.formattedAddress,"
                    "places.types,places.rating,places.googleMapsUri"
                ),
            },
            json={"textQuery": query, "maxResultCount": 1},
        )

        if resp.status_code != 200:
            return EntityResolutionResult(
                success=False, error=f"Google Maps API error: {resp.status_code}"
            )

        data = resp.json()
        places = data.get("places", [])
        if not places:
            return EntityResolutionResult(success=False, error="No places found")

        place = places[0]
        display_name = place.get("displayName", {}).get("text", query)

        return EntityResolutionResult(
            success=True,
            entity=ResolvedEntity(
                entity_type="place",
                surface=query,
                name=display_name,
                metadata={
                    "address": place.get("formattedAddress"),
                    "types": place.get("types", []),
                    "rating": place.get("rating"),
                    "maps_url": place.get("googleMapsUri"),
                },
            ),
        )

    except httpx.TimeoutException:
        return EntityResolutionResult(success=False, error="Google Maps request timed out")
    except httpx.HTTPError as e:
        return EntityResolutionResult(success=False, error=f"Google Maps request failed: {e}")


# ---------------------------------------------------------------------------
# Google Books
# ---------------------------------------------------------------------------


async def resolve_book(
    api_key: str | None,
    query: str,
) -> EntityResolutionResult:
    """Resolve a book title using Google Books API.

    Args:
        api_key: Google Books API key (optional — public endpoint works without).
        query: Book title to search for.

    Returns:
        EntityResolutionResult with book data or error.
    """
    try:
        params: dict[str, str] = {"q": query, "maxResults": "1"}
        if api_key:
            params["key"] = api_key

        resp = await _request_with_retry(
            "get",
            "https://www.googleapis.com/books/v1/volumes",
            params=params,
        )

        if resp.status_code != 200:
            return EntityResolutionResult(
                success=False, error=f"Google Books API error: {resp.status_code}"
            )

        data = resp.json()
        items = data.get("items", [])
        if not items:
            return EntityResolutionResult(success=False, error="No books found")

        vol = items[0].get("volumeInfo", {})
        title = vol.get("title", query)

        return EntityResolutionResult(
            success=True,
            entity=ResolvedEntity(
                entity_type="book",
                surface=query,
                name=title,
                metadata={
                    "authors": vol.get("authors", []),
                    "published_date": vol.get("publishedDate"),
                    "description": (vol.get("description") or "")[:300],
                    "categories": vol.get("categories", []),
                    "thumbnail": vol.get("imageLinks", {}).get("thumbnail"),
                },
            ),
        )

    except httpx.TimeoutException:
        return EntityResolutionResult(success=False, error="Google Books request timed out")
    except httpx.HTTPError as e:
        return EntityResolutionResult(success=False, error=f"Google Books request failed: {e}")


# ---------------------------------------------------------------------------
# TMDB (Movies & TV)
# ---------------------------------------------------------------------------


async def resolve_movie_or_tv(
    api_key: str,
    query: str,
) -> EntityResolutionResult:
    """Resolve a movie or TV show using TMDB multi-search.

    Args:
        api_key: TMDB API key (v3 auth).
        query: Movie or TV show title to search for.

    Returns:
        EntityResolutionResult with movie/TV data or error.
    """
    try:
        resp = await _request_with_retry(
            "get",
            "https://api.themoviedb.org/3/search/multi",
            params={"api_key": api_key, "query": query, "page": "1"},
        )

        if resp.status_code != 200:
            return EntityResolutionResult(
                success=False, error=f"TMDB API error: {resp.status_code}"
            )

        data = resp.json()
        results = data.get("results", [])

        # Filter to movie/tv only
        results = [r for r in results if r.get("media_type") in ("movie", "tv")]
        if not results:
            return EntityResolutionResult(success=False, error="No movies/TV shows found")

        item = results[0]
        media_type = item["media_type"]
        name = item.get("title") or item.get("name") or query

        poster = item.get("poster_path")
        poster_url = f"https://image.tmdb.org/t/p/w500{poster}" if poster else None

        return EntityResolutionResult(
            success=True,
            entity=ResolvedEntity(
                entity_type=media_type,
                surface=query,
                name=name,
                metadata={
                    "tmdb_id": item.get("id"),
                    "overview": (item.get("overview") or "")[:300],
                    "release_date": item.get("release_date") or item.get("first_air_date"),
                    "vote_average": item.get("vote_average"),
                    "poster_url": poster_url,
                },
            ),
        )

    except httpx.TimeoutException:
        return EntityResolutionResult(success=False, error="TMDB request timed out")
    except httpx.HTTPError as e:
        return EntityResolutionResult(success=False, error=f"TMDB request failed: {e}")


# ---------------------------------------------------------------------------
# Spotify
# ---------------------------------------------------------------------------

# Module-level cache for Spotify access token with TTL
_spotify_token: str | None = None
_spotify_token_expires: float = 0.0


async def _get_spotify_token(client_id: str, client_secret: str) -> str | None:
    """Get a Spotify access token via client credentials flow.

    Caches the token with a TTL (expires 100s before actual expiry for safety).
    """
    global _spotify_token, _spotify_token_expires
    if _spotify_token and time.time() < _spotify_token_expires:
        return _spotify_token

    try:
        client = _get_client()
        resp = await client.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
        )

        if resp.status_code != 200:
            logger.warning({"event": "spotify_auth_error", "status": resp.status_code})
            return None

        data = resp.json()
        _spotify_token = data.get("access_token")
        # Spotify tokens expire in 3600s; refresh 100s early
        expires_in = data.get("expires_in", 3600)
        _spotify_token_expires = time.time() + expires_in - 100
        return _spotify_token

    except httpx.HTTPError as e:
        logger.warning({"event": "spotify_auth_failed", "error": str(e)})
        return None


async def resolve_music(
    client_id: str,
    client_secret: str,
    query: str,
) -> EntityResolutionResult:
    """Resolve a song or artist using Spotify Search API.

    Args:
        client_id: Spotify client ID.
        client_secret: Spotify client secret.
        query: Song or artist name to search for.

    Returns:
        EntityResolutionResult with music data or error.
    """
    token = await _get_spotify_token(client_id, client_secret)
    if not token:
        return EntityResolutionResult(success=False, error="Failed to authenticate with Spotify")

    try:
        resp = await _request_with_retry(
            "get",
            "https://api.spotify.com/v1/search",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": query, "type": "track", "limit": "1"},
        )

        if resp.status_code == 401:
            # Token expired, clear cache and retry once
            global _spotify_token, _spotify_token_expires
            _spotify_token = None
            _spotify_token_expires = 0.0
            token = await _get_spotify_token(client_id, client_secret)
            if not token:
                return EntityResolutionResult(success=False, error="Spotify re-auth failed")
            resp = await _request_with_retry(
                "get",
                "https://api.spotify.com/v1/search",
                headers={"Authorization": f"Bearer {token}"},
                params={"q": query, "type": "track", "limit": "1"},
            )

        if resp.status_code != 200:
            return EntityResolutionResult(
                success=False, error=f"Spotify API error: {resp.status_code}"
            )

        data = resp.json()
        tracks = data.get("tracks", {}).get("items", [])
        if not tracks:
            return EntityResolutionResult(success=False, error="No tracks found")

        track = tracks[0]
        artists = [a.get("name", "") for a in track.get("artists", [])]

        return EntityResolutionResult(
            success=True,
            entity=ResolvedEntity(
                entity_type="music",
                surface=query,
                name=track.get("name", query),
                metadata={
                    "artists": artists,
                    "album": track.get("album", {}).get("name"),
                    "spotify_url": track.get("external_urls", {}).get("spotify"),
                    "preview_url": track.get("preview_url"),
                    "album_art": (
                        track.get("album", {}).get("images", [{}])[0].get("url")
                        if track.get("album", {}).get("images")
                        else None
                    ),
                },
            ),
        )

    except httpx.TimeoutException:
        return EntityResolutionResult(success=False, error="Spotify request timed out")
    except httpx.HTTPError as e:
        return EntityResolutionResult(success=False, error=f"Spotify request failed: {e}")


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

# Map entity types to their resolver
ENTITY_TYPE_MAP = {
    "place": "place",
    "restaurant": "place",
    "location": "place",
    "book": "book",
    "movie": "movie_or_tv",
    "tv": "movie_or_tv",
    "tv_show": "movie_or_tv",
    "show": "movie_or_tv",
    "music": "music",
    "song": "music",
    "artist": "music",
}


async def resolve_entity(
    entity_type: str,
    query: str,
    *,
    google_maps_api_key: str | None,
    google_books_api_key: str | None,
    tmdb_api_key: str | None,
    spotify_client_id: str | None,
    spotify_client_secret: str | None,
) -> EntityResolutionResult:
    """Dispatch entity resolution to the appropriate API.

    Args:
        entity_type: Type of entity (place, book, movie, tv, music, etc.).
        query: The surface-form text to resolve.
        google_maps_api_key: Google Maps API key (None = resolver unavailable).
        google_books_api_key: Google Books API key (optional).
        tmdb_api_key: TMDB API key (None = resolver unavailable).
        spotify_client_id: Spotify client ID (None = resolver unavailable).
        spotify_client_secret: Spotify client secret (None = resolver unavailable).

    Returns:
        EntityResolutionResult with resolved entity or error.
    """
    resolver_type = ENTITY_TYPE_MAP.get(entity_type.lower())

    if resolver_type is None:
        return EntityResolutionResult(success=False, error=f"Unknown entity type: {entity_type}")

    if resolver_type == "place":
        if not google_maps_api_key:
            return EntityResolutionResult(success=False, error="Google Maps API key not configured")
        return await resolve_place(google_maps_api_key, query)
    elif resolver_type == "book":
        return await resolve_book(google_books_api_key, query)
    elif resolver_type == "movie_or_tv":
        if not tmdb_api_key:
            return EntityResolutionResult(success=False, error="TMDB API key not configured")
        return await resolve_movie_or_tv(tmdb_api_key, query)
    elif resolver_type == "music":
        if not spotify_client_id or not spotify_client_secret:
            return EntityResolutionResult(success=False, error="Spotify credentials not configured")
        return await resolve_music(spotify_client_id, spotify_client_secret, query)
    else:
        return EntityResolutionResult(success=False, error=f"No resolver for: {resolver_type}")
