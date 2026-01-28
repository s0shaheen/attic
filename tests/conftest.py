"""
Pytest fixtures for TikTok export test data.

This module provides fixtures for testing the TikTok data processing pipeline.
Fixtures are organized by scope and use case.

Fixture Types:
- Session-scoped: Loaded once per test session (large files)
- Function-scoped: Fresh for each test (edge cases that may be mutated)
- Factory fixtures: Build custom data on demand

Usage:
    def test_parser(tiktok_export_minimal):
        assert "Likes and Favorites" in tiktok_export_minimal

    def test_edge_case(tiktok_export_empty):
        result = parse_export(tiktok_export_empty)
        assert result.items == []

    def test_custom_data(tiktok_liked_video_factory):
        video = tiktok_liked_video_factory(date="2024-01-01")
        ...
"""

import json
from pathlib import Path
from typing import Any, Callable, Optional

import pytest

# Base path for all TikTok export fixtures
FIXTURES_BASE = Path(__file__).parent / "fixtures" / "tiktok-exports"


def _load_json(path: Path) -> dict:
    """Load JSON file, returning empty dict if not found."""
    if not path.exists():
        pytest.skip(f"Fixture file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# =============================================================================
# Session-scoped fixtures (loaded once per test session)
# =============================================================================


@pytest.fixture(scope="session")
def tiktok_export_full_anonymized() -> dict:
    """
    Full anonymized TikTok export with all sections.

    Contains:
    - ~5,989 likes
    - ~903 favorites
    - ~16,184 watch history
    - ~87 comments
    - Profile, settings, DMs, etc.

    Use for integration tests and search tests.
    """
    return _load_json(FIXTURES_BASE / "anonymized" / "full_anonymized.json")


@pytest.fixture(scope="session")
def tiktok_export_minimal() -> dict:
    """
    Minimal slice with 1-5 items per category.

    Use for fast unit tests where you need the full structure
    but don't need large data volumes.
    """
    return _load_json(FIXTURES_BASE / "slices" / "minimal.json")


@pytest.fixture(scope="session")
def tiktok_export_likes_only() -> dict:
    """
    Just the Likes and Favorites section.

    Use for testing like processing, URL extraction, etc.
    """
    return _load_json(FIXTURES_BASE / "slices" / "likes_only.json")


@pytest.fixture(scope="session")
def tiktok_export_favorites_only() -> dict:
    """
    Just the Favorite Videos subsection.

    Use for testing favorites-specific processing.
    """
    return _load_json(FIXTURES_BASE / "slices" / "favorites_only.json")


@pytest.fixture(scope="session")
def tiktok_export_watch_history_only() -> dict:
    """
    Just the Watch History section (~16K items).

    Use for performance testing and pagination tests.
    """
    return _load_json(FIXTURES_BASE / "slices" / "watch_history_only.json")


@pytest.fixture(scope="session")
def tiktok_export_comments_only() -> dict:
    """
    Just the Comments section.

    Use for testing comment parsing and text processing.
    """
    return _load_json(FIXTURES_BASE / "slices" / "comments_only.json")


@pytest.fixture(scope="session")
def tiktok_export_user_alice() -> dict:
    """
    Synthetic power user (500 likes, 2000 watch history).

    Use for multi-user scenarios and volume testing.
    """
    return _load_json(FIXTURES_BASE / "synthetic" / "user_alice.json")


@pytest.fixture(scope="session")
def tiktok_export_user_bob() -> dict:
    """
    Synthetic casual user (50 likes, 100 watch history).

    Use for multi-user scenarios and comparing user behaviors.
    """
    return _load_json(FIXTURES_BASE / "synthetic" / "user_bob.json")


# =============================================================================
# Function-scoped fixtures (fresh for each test - edge cases)
# =============================================================================


@pytest.fixture
def tiktok_export_empty() -> dict:
    """
    Valid export structure with empty arrays.

    Use for testing empty state handling.
    """
    return _load_json(FIXTURES_BASE / "edge_cases" / "empty_export.json")


@pytest.fixture
def tiktok_export_missing_fields() -> dict:
    """
    Export with missing expected fields.

    Use for testing graceful degradation and error handling.
    """
    return _load_json(FIXTURES_BASE / "edge_cases" / "missing_fields.json")


@pytest.fixture
def tiktok_export_null_values() -> dict:
    """
    Export with null values in various places.

    Use for testing null handling throughout the pipeline.
    """
    return _load_json(FIXTURES_BASE / "edge_cases" / "null_values.json")


@pytest.fixture
def tiktok_export_extra_fields() -> dict:
    """
    Export with unknown/new fields.

    Use for testing forward compatibility.
    """
    return _load_json(FIXTURES_BASE / "edge_cases" / "extra_fields.json")


@pytest.fixture
def tiktok_export_malformed_json_path() -> Path:
    """
    Path to malformed JSON file.

    Returns the path instead of loading, since it can't be parsed.
    Use for testing JSON parsing error handling.
    """
    path = FIXTURES_BASE / "edge_cases" / "malformed_json.txt"
    if not path.exists():
        pytest.skip(f"Fixture file not found: {path}")
    return path


# =============================================================================
# Factory fixtures (build custom data on demand)
# =============================================================================


@pytest.fixture
def tiktok_export_builder() -> Callable[..., dict]:
    """
    Factory to build custom TikTok export structures.

    Usage:
        def test_custom(tiktok_export_builder):
            export = tiktok_export_builder(
                likes_count=10,
                include_comments=True
            )
    """
    def builder(
        likes_count: int = 0,
        favorites_count: int = 0,
        watch_history_count: int = 0,
        comments_count: int = 0,
        include_profile: bool = True,
        include_dms: bool = False
    ) -> dict:
        export: dict[str, Any] = {}

        if likes_count > 0 or favorites_count > 0:
            export["Likes and Favorites"] = {}
            if likes_count > 0:
                export["Likes and Favorites"]["Like List"] = {
                    "ItemFavoriteList": [
                        {"date": f"2024-01-{i+1:02d} 12:00:00", "link": f"https://tiktok.com/v/{i}"}
                        for i in range(likes_count)
                    ]
                }
            if favorites_count > 0:
                export["Likes and Favorites"]["Favorite Videos"] = {
                    "FavoriteVideoList": [
                        {"date": f"2024-01-{i+1:02d} 12:00:00", "link": f"https://tiktok.com/v/fav{i}"}
                        for i in range(favorites_count)
                    ]
                }

        if watch_history_count > 0:
            export["Your Activity"] = {
                "Watch History": {
                    "VideoList": [
                        {"Date": f"2024-01-{i+1:02d} 12:00:00", "Link": f"https://tiktok.com/v/watch{i}"}
                        for i in range(watch_history_count)
                    ]
                }
            }

        if comments_count > 0:
            export["Comment"] = {
                "Comments": {
                    "App": 1,
                    "CommentsList": [
                        {"date": f"2024-01-{i+1:02d} 12:00:00", "comment": f"Comment {i}", "photo": "N/A", "url": ""}
                        for i in range(comments_count)
                    ]
                }
            }

        if include_profile:
            export["Profile And Settings"] = {
                "Profile Info": {
                    "App": 1,
                    "ProfileMap": {
                        "userName": "test_user",
                        "bioDescription": "Test bio"
                    }
                }
            }

        if include_dms:
            export["Direct Message"] = {
                "Direct Messages": {
                    "ChatHistory": {}
                }
            }

        return export

    return builder


@pytest.fixture
def tiktok_video_url_factory() -> Callable[..., str]:
    """
    Factory to generate TikTok video URLs.

    Usage:
        def test_url(tiktok_video_url_factory):
            url = tiktok_video_url_factory(video_id="123456789")
    """
    def factory(video_id: Optional[str] = None) -> str:
        if video_id is None:
            import random
            video_id = str(random.randint(1000000000000000000, 9999999999999999999))
        return f"https://www.tiktokv.com/share/video/{video_id}"

    return factory


@pytest.fixture
def tiktok_liked_video_factory() -> Callable[..., dict]:
    """
    Factory to generate individual liked video entries.

    Usage:
        def test_like(tiktok_liked_video_factory):
            like = tiktok_liked_video_factory(date="2024-06-15")
    """
    def factory(
        date: str = "2024-01-01 12:00:00",
        video_id: Optional[str] = None
    ) -> dict:
        if video_id is None:
            import random
            video_id = str(random.randint(1000000000000000000, 9999999999999999999))
        return {
            "date": date,
            "link": f"https://www.tiktokv.com/share/video/{video_id}"
        }

    return factory


@pytest.fixture
def tiktok_comment_factory() -> Callable[..., dict]:
    """
    Factory to generate individual comment entries.

    Usage:
        def test_comment(tiktok_comment_factory):
            comment = tiktok_comment_factory(text="Great video!")
    """
    def factory(
        text: str = "Test comment",
        date: str = "2024-01-01 12:00:00",
        url: str = ""
    ) -> dict:
        return {
            "date": date,
            "comment": text,
            "photo": "N/A",
            "url": url
        }

    return factory


# =============================================================================
# Utility fixtures
# =============================================================================


@pytest.fixture
def tiktok_fixtures_base_path() -> Path:
    """
    Get the base path for TikTok fixtures.

    Use when you need direct file access.
    """
    return FIXTURES_BASE
