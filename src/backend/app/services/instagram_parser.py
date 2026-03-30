"""Instagram export ZIP file parser.

This module provides functionality to parse Instagram data export ZIP files
and extract saved posts and user-created collections (saved folders).

Security features:
- Path traversal prevention (zip-slip defense)
- No absolute paths allowed in ZIP entries
- No symbolic link following
- Memory-safe extraction via streaming

Data privacy:
- Only accesses whitelisted files (saved posts, saved collections)
- Never reads DMs, comments, stories, or other data
- Logs counts only, not content

Example usage:
    from app.services.instagram_parser import parse_instagram_export, get_export_summary

    # Parse entire export
    result = parse_instagram_export(zip_path)

    # Get quick summary without full parsing
    summary = get_export_summary(zip_path)
"""

import json
import logging
import os
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import IO

from app.schemas.instagram_export import (
    EmptyExportError,
    InstagramCollectionItemRef,
    InstagramCollectionRef,
    InstagramExportSummary,
    InstagramParsedExport,
    InstagramPostReference,
    InvalidExportError,
    ZipSecurityError,
)

logger = logging.getLogger(__name__)

# Whitelisted paths within the Instagram export
# These are the ONLY files we access — everything else is ignored
SAVED_POSTS_PATH = "your_instagram_activity/saved/saved_posts.json"
SAVED_COLLECTIONS_PATH = "your_instagram_activity/saved/saved_collections.json"

# Maximum file size to extract (25MB — IG saved posts files can be larger than TikTok's)
MAX_EXTRACT_SIZE = 25 * 1024 * 1024


# ---------------------------------------------------------------------------
# ZIP security helpers (mirrors tiktok_parser.py)
# ---------------------------------------------------------------------------


def _is_safe_path(zip_path: str) -> bool:
    """Check if a path within the ZIP is safe to extract.

    Defends against path traversal attacks, absolute paths,
    and paths that would escape the extraction directory.
    """
    path = PurePosixPath(zip_path)

    if path.is_absolute():
        return False

    if ".." in path.parts:
        return False

    try:
        normalized = os.path.normpath(zip_path)
        if normalized.startswith("..") or normalized.startswith("/"):
            return False
    except (ValueError, TypeError):
        return False

    return True


def _validate_zip_entry(info: zipfile.ZipInfo) -> bool:
    """Validate a single ZIP entry for security issues."""
    if not _is_safe_path(info.filename):
        logger.warning(
            {
                "event": "zip_security_check_failed",
                "reason": "path_traversal",
                "filename": info.filename[:100],
            }
        )
        return False

    # Check for symbolic links (unix mode bit)
    if (info.external_attr >> 16) & 0o170000 == 0o120000:
        logger.warning(
            {
                "event": "zip_security_check_failed",
                "reason": "symbolic_link",
                "filename": info.filename[:100],
            }
        )
        return False

    if info.file_size > MAX_EXTRACT_SIZE:
        logger.warning(
            {
                "event": "zip_security_check_failed",
                "reason": "file_too_large",
                "filename": info.filename[:100],
                "size": info.file_size,
                "max_size": MAX_EXTRACT_SIZE,
            }
        )
        return False

    return True


def _open_zip_file(zip_file: IO[bytes] | Path) -> zipfile.ZipFile:
    """Open a ZIP file from either a file path or file-like object."""
    try:
        return zipfile.ZipFile(zip_file, "r")
    except zipfile.BadZipFile:
        raise InvalidExportError(
            "The uploaded file is not a valid ZIP archive",
            details={"reason": "not_a_zip"},
        )
    except Exception as e:
        raise InvalidExportError(
            f"Failed to open ZIP file: {e!s}",
            details={"reason": "open_failed", "error": str(e)},
        )


def _validate_zip_security(zf: zipfile.ZipFile) -> None:
    """Validate all entries in the ZIP for security issues."""
    for info in zf.infolist():
        if not _validate_zip_entry(info):
            raise ZipSecurityError(
                "ZIP file contains potentially unsafe entries",
                details={
                    "filename": info.filename[:100],
                    "reason": "security_validation_failed",
                },
            )


def _read_json_from_zip(zf: zipfile.ZipFile, path: str) -> dict:
    """Safely read and parse a JSON file from the ZIP."""
    try:
        with zf.open(path) as f:
            content = f.read(MAX_EXTRACT_SIZE)
            return json.loads(content.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise InvalidExportError(
            f"Malformed JSON in {path}",
            details={"path": path, "error": str(e), "reason": "json_decode_error"},
        )
    except UnicodeDecodeError as e:
        raise InvalidExportError(
            f"Invalid encoding in {path}",
            details={"path": path, "error": str(e), "reason": "encoding_error"},
        )
    except Exception as e:
        raise InvalidExportError(
            f"Failed to read {path}: {e!s}",
            details={"path": path, "error": str(e), "reason": "read_error"},
        )


# ---------------------------------------------------------------------------
# Instagram-specific parsing
# ---------------------------------------------------------------------------


def _timestamp_to_datetime(ts: int | float | None) -> datetime:
    """Convert a unix timestamp to a datetime.

    Args:
        ts: Unix timestamp (seconds since epoch), or None.

    Returns:
        datetime in UTC, or current time if ts is None/invalid.
    """
    if ts is None:
        return datetime.now(UTC)
    try:
        return datetime.fromtimestamp(int(ts), tz=UTC)
    except (ValueError, OSError, OverflowError):
        return datetime.now(UTC)


def _parse_saved_posts(data: dict) -> list[InstagramPostReference]:
    """Parse saved posts from the Instagram export.

    Expected structure:
    {
      "saved_saved_media": [
        {
          "title": "creator_username",
          "string_map_data": {
            "Saved on": {
              "href": "https://www.instagram.com/reel/ABC/",
              "timestamp": 1774223235
            }
          }
        }
      ]
    }

    Args:
        data: Parsed JSON from saved_posts.json.

    Returns:
        List of InstagramPostReference objects.
    """
    posts: list[InstagramPostReference] = []

    items = data.get("saved_saved_media")
    if not items or not isinstance(items, list):
        return posts

    for item in items:
        if not isinstance(item, dict):
            continue

        creator = item.get("title", "")
        saved_on = item.get("string_map_data", {}).get("Saved on", {})

        url = saved_on.get("href")
        if not url:
            continue

        timestamp = _timestamp_to_datetime(saved_on.get("timestamp"))

        posts.append(
            InstagramPostReference(
                url=url,
                timestamp=timestamp,
                creator_username=creator or "",
            )
        )

    return posts


def _parse_saved_collections(
    data: dict,
) -> list[InstagramCollectionRef]:
    """Parse user-created collections from the Instagram export.

    The format is a flat array where collection headers (entries with
    title == "Collection") are followed by their items sequentially.

    Expected structure:
    {
      "saved_saved_collections": [
        {
          "title": "Collection",
          "string_map_data": {
            "Name": { "value": "Food n recipes" },
            "Creation Time": { "timestamp": 1710355922 },
            "Update Time": { "timestamp": 1725770652 }
          }
        },
        {
          "string_map_data": {
            "Name": {
              "href": "https://www.instagram.com/reel/ABC/",
              "value": "creator_username"
            },
            "Added Time": { "timestamp": 1727979858 }
          }
        },
        ...
      ]
    }

    Args:
        data: Parsed JSON from saved_collections.json.

    Returns:
        List of InstagramCollectionRef objects with their items.
    """
    collections: list[InstagramCollectionRef] = []

    items = data.get("saved_saved_collections")
    if not items or not isinstance(items, list):
        return collections

    current_collection: InstagramCollectionRef | None = None

    for entry in items:
        if not isinstance(entry, dict):
            continue

        string_map = entry.get("string_map_data", {})

        # Collection header: has title == "Collection" and Name.value (no href)
        if entry.get("title") == "Collection":
            # Save the previous collection if it exists
            if current_collection is not None:
                collections.append(current_collection)

            name_data = string_map.get("Name", {})
            name = name_data.get("value", "Untitled")
            created_ts = string_map.get("Creation Time", {}).get("timestamp")
            updated_ts = string_map.get("Update Time", {}).get("timestamp")

            current_collection = InstagramCollectionRef(
                name=name,
                created_at=_timestamp_to_datetime(created_ts),
                updated_at=_timestamp_to_datetime(updated_ts),
                items=[],
            )

        # Collection item: has Name.href (URL) and Added Time
        elif current_collection is not None:
            name_data = string_map.get("Name", {})
            url = name_data.get("href")
            creator = name_data.get("value", "")
            added_ts = string_map.get("Added Time", {}).get("timestamp")

            if url:
                current_collection.items.append(
                    InstagramCollectionItemRef(
                        url=url,
                        creator_username=creator or "",
                        added_at=_timestamp_to_datetime(added_ts),
                    )
                )

    # Don't forget the last collection
    if current_collection is not None:
        collections.append(current_collection)

    return collections


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_instagram_export(
    zip_file: IO[bytes] | Path,
) -> InstagramParsedExport:
    """Parse an Instagram data export ZIP file.

    Extracts saved posts and user-created collections.
    Only accesses whitelisted files.

    Args:
        zip_file: File-like object or path to ZIP file.

    Returns:
        InstagramParsedExport with extracted data.

    Raises:
        InvalidExportError: Export structure is invalid.
        EmptyExportError: No saved posts found.
        ZipSecurityError: ZIP file failed security checks.
    """
    logger.info({"event": "instagram_parse_started"})

    with _open_zip_file(zip_file) as zf:
        _validate_zip_security(zf)

        zip_names = set(zf.namelist())

        # Saved posts
        saved_posts: list[InstagramPostReference] = []
        if SAVED_POSTS_PATH in zip_names:
            saved_data = _read_json_from_zip(zf, SAVED_POSTS_PATH)
            saved_posts = _parse_saved_posts(saved_data)

        # Collections (optional — not all users have collections)
        collections: list[InstagramCollectionRef] = []
        if SAVED_COLLECTIONS_PATH in zip_names:
            collections_data = _read_json_from_zip(zf, SAVED_COLLECTIONS_PATH)
            collections = _parse_saved_collections(collections_data)

        # If saved_posts is empty, extract URLs from collection items as fallback
        if not saved_posts and collections:
            saved_urls: set[str] = set()
            for coll in collections:
                for item in coll.items:
                    if item.url and item.url not in saved_urls:
                        saved_urls.add(item.url)
                        saved_posts.append(
                            InstagramPostReference(
                                url=item.url,
                                timestamp=item.added_at,
                                creator_username=item.creator_username,
                            )
                        )

    if not saved_posts and not collections:
        # Re-open to check what files exist for a useful error message
        with _open_zip_file(zip_file) as zf2:
            zip_names2 = set(zf2.namelist())
        if SAVED_POSTS_PATH not in zip_names2 and SAVED_COLLECTIONS_PATH not in zip_names2:
            raise InvalidExportError(
                "The ZIP file doesn't contain Instagram saved posts or collections data",
                details={
                    "reason": "missing_data_files",
                    "expected_paths": [SAVED_POSTS_PATH, SAVED_COLLECTIONS_PATH],
                },
            )
        raise EmptyExportError(
            "No saved posts or collection items found in the Instagram export",
            details={"reason": "empty_export"},
        )

    summary = InstagramExportSummary(
        saved_count=len(saved_posts),
        collection_count=len(collections),
        collection_names=[c.name for c in collections],
    )

    logger.info(
        {
            "event": "instagram_parse_complete",
            "saved_count": len(saved_posts),
            "collection_count": len(collections),
        }
    )

    return InstagramParsedExport(
        summary=summary,
        saved_posts=saved_posts,
        collections=collections,
    )


def get_export_summary(zip_file: IO[bytes] | Path) -> InstagramExportSummary:
    """Get a quick summary of Instagram export contents.

    Used for scope selection UI to show counts before processing.

    Args:
        zip_file: File-like object or path to ZIP file.

    Returns:
        InstagramExportSummary with post and collection counts.

    Raises:
        InvalidExportError: Export structure is invalid.
        ZipSecurityError: ZIP file failed security checks.
    """
    result = parse_instagram_export(zip_file)
    return result.summary
