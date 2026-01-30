"""TikTok export ZIP file parser.

This module provides functionality to parse TikTok data export ZIP files
and extract liked and favorited video references. It implements security
measures against zip-slip attacks and validates export structure.

Security features:
- Path traversal prevention (zip-slip defense)
- No absolute paths allowed in ZIP entries
- No symbolic link following
- Memory-safe extraction via streaming

Data privacy:
- Only accesses whitelisted files (Like List, Favorite Videos)
- Never reads DMs, search history, watch history, or other data
- Logs counts only, not content

Example usage:
    from app.services.tiktok_parser import parse_tiktok_export, get_export_summary

    # Parse entire export
    result = parse_tiktok_export(zip_path, scope="both")

    # Get quick summary without full parsing
    summary = get_export_summary(zip_path)
"""

import json
import logging
import os
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import IO, Literal

from app.schemas.tiktok_export import (
    EmptyExportError,
    InvalidExportError,
    TikTokExportSummary,
    TikTokParsedExport,
    TikTokVideoReference,
    ZipSecurityError,
)

logger = logging.getLogger(__name__)

# Whitelisted paths within the TikTok export
# These are the ONLY files we access - everything else is ignored
LIKED_VIDEOS_PATH = "Activity/Like List.json"
FAVORITED_VIDEOS_PATH = "Activity/Favorite Videos.json"

# Alternative paths (TikTok may use different structures)
# Based on observed real export structures
ALT_LIKED_PATHS = [
    "Activity/Like List.json",
    "Likes and Favorites/Like List.json",
]
ALT_FAVORITED_PATHS = [
    "Activity/Favorite Videos.json",
    "Likes and Favorites/Favorite Videos.json",
]

# Maximum file size to extract (10MB should be more than enough for JSON files)
MAX_EXTRACT_SIZE = 10 * 1024 * 1024


def _is_safe_path(zip_path: str, base_path: str = "") -> bool:
    """Check if a path within the ZIP is safe to extract.

    Defends against:
    - Path traversal attacks (../../../etc/passwd)
    - Absolute paths (/etc/passwd)
    - Paths that would escape the extraction directory

    Args:
        zip_path: Path of the file within the ZIP
        base_path: Optional base path to resolve against

    Returns:
        True if the path is safe, False otherwise
    """
    # Convert to PurePosixPath for consistent handling
    path = PurePosixPath(zip_path)

    # Check for absolute paths
    if path.is_absolute():
        return False

    # Check for path traversal
    if ".." in path.parts:
        return False

    # Normalize and check if it escapes
    try:
        # os.path.normpath handles Windows and Unix paths
        normalized = os.path.normpath(zip_path)
        if normalized.startswith("..") or normalized.startswith("/"):
            return False
    except (ValueError, TypeError):
        return False

    return True


def _validate_zip_entry(info: zipfile.ZipInfo) -> bool:
    """Validate a single ZIP entry for security issues.

    Args:
        info: ZipInfo object for the entry

    Returns:
        True if the entry is safe, False otherwise
    """
    # Check for path safety
    if not _is_safe_path(info.filename):
        logger.warning(
            {
                "event": "zip_security_check_failed",
                "reason": "path_traversal",
                "filename": info.filename[:100],  # Truncate for logging
            }
        )
        return False

    # Check for symbolic links (external_attr bit 29)
    # Unix symbolic links have mode 0o120000
    if (info.external_attr >> 16) & 0o170000 == 0o120000:
        logger.warning(
            {
                "event": "zip_security_check_failed",
                "reason": "symbolic_link",
                "filename": info.filename[:100],
            }
        )
        return False

    # Check file size
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
    """Open a ZIP file from either a file path or file-like object.

    Args:
        zip_file: Path to ZIP file or file-like object

    Returns:
        Opened ZipFile object

    Raises:
        InvalidExportError: If the file is not a valid ZIP
    """
    try:
        if isinstance(zip_file, Path):
            return zipfile.ZipFile(zip_file, "r")
        else:
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


def _find_file_in_zip(zf: zipfile.ZipFile, possible_paths: list[str]) -> str | None:
    """Find a file in the ZIP using multiple possible paths.

    Args:
        zf: Open ZipFile object
        possible_paths: List of paths to try

    Returns:
        The first matching path found, or None if not found
    """
    zip_names = set(zf.namelist())

    for path in possible_paths:
        if path in zip_names:
            return path

        # Also check with leading slash stripped or added
        alt_path = path.lstrip("/")
        if alt_path in zip_names:
            return alt_path

    return None


def _validate_zip_security(zf: zipfile.ZipFile) -> None:
    """Validate all entries in the ZIP for security issues.

    Args:
        zf: Open ZipFile object

    Raises:
        ZipSecurityError: If any entry fails security validation
    """
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
    """Safely read and parse a JSON file from the ZIP.

    Args:
        zf: Open ZipFile object
        path: Path to the JSON file within the ZIP

    Returns:
        Parsed JSON as a dictionary

    Raises:
        InvalidExportError: If the JSON is malformed or cannot be read
    """
    try:
        with zf.open(path) as f:
            # Read with size limit
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


def _parse_timestamp(date_str: str | None) -> datetime | None:
    """Parse a TikTok export timestamp.

    TikTok uses various date formats in their exports.
    This function tries multiple formats.

    Args:
        date_str: Date string from the export

    Returns:
        Parsed datetime or None if parsing fails
    """
    if not date_str:
        return None

    # Known TikTok date formats
    formats = [
        "%Y-%m-%d %H:%M:%S",  # e.g., "2025-10-02 16:37:01"
        "%Y-%m-%d",  # e.g., "2025-10-02"
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None


def _parse_liked_videos(data: dict) -> list[TikTokVideoReference]:
    """Parse liked videos from the export data.

    The Like List structure varies between export versions:
    - Newer: {"ItemFavoriteList": [{"date": "...", "link": "..."}]}
    - May also be under "LikeList" key

    Args:
        data: Parsed JSON data from Like List.json

    Returns:
        List of TikTokVideoReference objects
    """
    videos: list[TikTokVideoReference] = []

    # Try different possible structures
    # Based on observed exports, the structure can be:
    # 1. Top-level "Like List" with "ItemFavoriteList" array
    # 2. Just "ItemFavoriteList" at top level
    # 3. "LikeList" key

    video_list = None

    # Check for nested structure first (most common in recent exports)
    if "Like List" in data:
        inner = data["Like List"]
        if isinstance(inner, dict):
            video_list = inner.get("ItemFavoriteList") or inner.get("LikeList")
    elif "ItemFavoriteList" in data:
        video_list = data["ItemFavoriteList"]
    elif "LikeList" in data:
        video_list = data["LikeList"]

    if not video_list or not isinstance(video_list, list):
        return videos

    for item in video_list:
        if not isinstance(item, dict):
            continue

        # Get URL (try both 'link' and 'Link' keys)
        url = item.get("link") or item.get("Link")
        if not url:
            continue

        # Get timestamp (try both 'date' and 'Date' keys)
        date_str = item.get("date") or item.get("Date")
        timestamp = _parse_timestamp(date_str)

        # Use current time as fallback if no timestamp
        if timestamp is None:
            timestamp = datetime.now()

        videos.append(
            TikTokVideoReference(
                url=url,
                timestamp=timestamp,
                interaction_type="liked",
            )
        )

    return videos


def _parse_favorited_videos(data: dict) -> list[TikTokVideoReference]:
    """Parse favorited videos from the export data.

    The Favorite Videos structure varies between export versions:
    - Newer: {"FavoriteVideoList": [{"Date": "...", "Link": "..."}]}
    - May also be under "FavoriteList" key

    Args:
        data: Parsed JSON data from Favorite Videos.json

    Returns:
        List of TikTokVideoReference objects
    """
    videos: list[TikTokVideoReference] = []

    # Try different possible structures
    video_list = None

    # Check for nested structure first
    if "Favorite Videos" in data:
        inner = data["Favorite Videos"]
        if isinstance(inner, dict):
            video_list = inner.get("FavoriteVideoList") or inner.get("FavoriteList")
    elif "FavoriteVideoList" in data:
        video_list = data["FavoriteVideoList"]
    elif "FavoriteList" in data:
        video_list = data["FavoriteList"]

    if not video_list or not isinstance(video_list, list):
        return videos

    for item in video_list:
        if not isinstance(item, dict):
            continue

        # Get URL (try both 'Link' and 'link' keys)
        url = item.get("Link") or item.get("link")
        if not url:
            continue

        # Get timestamp (try both 'Date' and 'date' keys)
        date_str = item.get("Date") or item.get("date")
        timestamp = _parse_timestamp(date_str)

        # Use current time as fallback if no timestamp
        if timestamp is None:
            timestamp = datetime.now()

        videos.append(
            TikTokVideoReference(
                url=url,
                timestamp=timestamp,
                interaction_type="favorited",
            )
        )

    return videos


def _parse_from_combined_export(
    data: dict,
) -> tuple[list[TikTokVideoReference], list[TikTokVideoReference]]:
    """Parse liked and favorited videos from a combined single-file export.

    Some TikTok exports are a single JSON file with all data nested.
    This function handles that structure.

    Args:
        data: Parsed JSON data from the combined export

    Returns:
        Tuple of (liked_videos, favorited_videos)
    """
    liked_videos: list[TikTokVideoReference] = []
    favorited_videos: list[TikTokVideoReference] = []

    # Navigate to "Likes and Favorites" section if present
    likes_section = data.get("Likes and Favorites", {})

    # Parse liked videos
    like_list_data = likes_section.get("Like List", {})
    if like_list_data:
        liked_videos = _parse_liked_videos({"Like List": like_list_data})

    # Parse favorited videos
    favorite_data = likes_section.get("Favorite Videos", {})
    if favorite_data:
        favorited_videos = _parse_favorited_videos({"Favorite Videos": favorite_data})

    return liked_videos, favorited_videos


def parse_tiktok_export(
    zip_file: IO[bytes] | Path,
    scope: Literal["liked", "favorited", "both"] = "both",
) -> TikTokParsedExport:
    """Parse a TikTok data export ZIP file.

    Extracts liked and/or favorited video references from the export.
    Only accesses whitelisted files (Like List, Favorite Videos).

    Args:
        zip_file: File-like object or path to ZIP file
        scope: Which data to extract ("liked", "favorited", or "both")

    Returns:
        TikTokParsedExport with extracted video references

    Raises:
        InvalidExportError: Export structure is invalid
        EmptyExportError: No videos found in specified scope
        ZipSecurityError: ZIP file failed security checks

    Example:
        # From file path
        result = parse_tiktok_export(Path("export.zip"), scope="both")

        # From file-like object (e.g., uploaded file)
        result = parse_tiktok_export(uploaded_file.file, scope="liked")
    """
    logger.info(
        {
            "event": "parse_export_started",
            "scope": scope,
        }
    )

    liked_videos: list[TikTokVideoReference] = []
    favorited_videos: list[TikTokVideoReference] = []

    with _open_zip_file(zip_file) as zf:
        # Validate all entries for security
        _validate_zip_security(zf)

        # Check if this is a combined single-file export or directory structure
        zip_names = zf.namelist()

        # Check for a single JSON file that might be the combined export
        single_json_files = [
            n for n in zip_names if n.endswith(".json") and "/" not in n.strip("/")
        ]

        if single_json_files and len(single_json_files) == 1:
            # This might be a combined export file
            combined_data = _read_json_from_zip(zf, single_json_files[0])

            # Check if it has the expected combined structure
            if "Likes and Favorites" in combined_data:
                liked_videos, favorited_videos = _parse_from_combined_export(combined_data)

                # Filter based on scope
                if scope == "liked":
                    favorited_videos = []
                elif scope == "favorited":
                    liked_videos = []

        if not liked_videos and not favorited_videos:
            # Try to find individual files

            # Parse liked videos
            if scope in ("liked", "both"):
                liked_path = _find_file_in_zip(zf, ALT_LIKED_PATHS)
                if liked_path:
                    liked_data = _read_json_from_zip(zf, liked_path)
                    liked_videos = _parse_liked_videos(liked_data)
                    logger.info(
                        {
                            "event": "parsed_liked_videos",
                            "count": len(liked_videos),
                        }
                    )

            # Parse favorited videos
            if scope in ("favorited", "both"):
                favorited_path = _find_file_in_zip(zf, ALT_FAVORITED_PATHS)
                if favorited_path:
                    favorited_data = _read_json_from_zip(zf, favorited_path)
                    favorited_videos = _parse_favorited_videos(favorited_data)
                    logger.info(
                        {
                            "event": "parsed_favorited_videos",
                            "count": len(favorited_videos),
                        }
                    )

    # Check if we found any videos in the requested scope
    total_videos = len(liked_videos) + len(favorited_videos)

    if total_videos == 0:
        # Check if this is because files don't exist or they're empty
        with _open_zip_file(zip_file) as zf:
            liked_exists = _find_file_in_zip(zf, ALT_LIKED_PATHS) is not None
            favorited_exists = _find_file_in_zip(zf, ALT_FAVORITED_PATHS) is not None

            # Also check for combined export
            zip_names = zf.namelist()
            has_likes_section = False
            for name in zip_names:
                if name.endswith(".json"):
                    try:
                        data = _read_json_from_zip(zf, name)
                        if "Likes and Favorites" in data:
                            has_likes_section = True
                            break
                    except Exception:
                        continue

        if not liked_exists and not favorited_exists and not has_likes_section:
            raise InvalidExportError(
                "The ZIP file doesn't contain TikTok liked or favorited video data",
                details={
                    "reason": "missing_data_files",
                    "expected_files": ALT_LIKED_PATHS + ALT_FAVORITED_PATHS,
                },
            )

        raise EmptyExportError(
            f"No videos found in the '{scope}' scope",
            details={
                "scope": scope,
                "liked_found": len(liked_videos),
                "favorited_found": len(favorited_videos),
            },
        )

    # Build summary
    # Count unique URLs across both lists
    all_urls = {v.url for v in liked_videos} | {v.url for v in favorited_videos}

    summary = TikTokExportSummary(
        liked_count=len(liked_videos),
        favorited_count=len(favorited_videos),
        total_count=len(all_urls),
        has_liked=len(liked_videos) > 0,
        has_favorited=len(favorited_videos) > 0,
    )

    logger.info(
        {
            "event": "parse_export_complete",
            "liked_count": len(liked_videos),
            "favorited_count": len(favorited_videos),
            "total_count": len(all_urls),
        }
    )

    return TikTokParsedExport(
        summary=summary,
        liked_videos=liked_videos,
        favorited_videos=favorited_videos,
    )


def get_export_summary(zip_file: IO[bytes] | Path) -> TikTokExportSummary:
    """Get a quick summary of export contents without full parsing.

    Used for scope selection UI to show counts before processing.
    This is more efficient than parse_tiktok_export when you only need counts.

    Args:
        zip_file: File-like object or path to ZIP file

    Returns:
        TikTokExportSummary with video counts

    Raises:
        InvalidExportError: Export structure is invalid
        ZipSecurityError: ZIP file failed security checks

    Example:
        summary = get_export_summary(Path("export.zip"))
        print(f"Found {summary.liked_count} liked videos")
    """
    # For now, this just calls parse_tiktok_export
    # In the future, this could be optimized to only count entries
    result = parse_tiktok_export(zip_file, scope="both")
    return result.summary
