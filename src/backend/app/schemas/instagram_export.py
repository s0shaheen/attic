"""Instagram export data models.

This module defines Pydantic models for parsing Instagram data export files.
Covers saved posts and user-created collections (saved folders).
"""

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field

# Regex to extract shortcode from Instagram URLs
# Matches: /p/ABC123/, /reel/ABC123/, /tv/ABC123/
_SHORTCODE_RE = re.compile(r"/(?:p|reel|tv)/([A-Za-z0-9_-]+)")


def extract_shortcode(url: str) -> str | None:
    """Extract the shortcode (platform ID) from an Instagram URL.

    Args:
        url: Instagram post/reel/tv URL.

    Returns:
        The shortcode string, or None if the URL doesn't match.
    """
    match = _SHORTCODE_RE.search(url)
    return match.group(1) if match else None


def infer_media_hint(url: str) -> Literal["reel", "post", "igtv"]:
    """Infer the media type hint from an Instagram URL pattern.

    Args:
        url: Instagram URL.

    Returns:
        "reel" for /reel/, "igtv" for /tv/, "post" for /p/ or unknown.
    """
    if "/reel/" in url:
        return "reel"
    if "/tv/" in url:
        return "igtv"
    return "post"


class InstagramPostReference(BaseModel):
    """A single saved post reference from the Instagram export.

    Attributes:
        url: Instagram post URL (e.g., https://www.instagram.com/reel/ABC123/)
        timestamp: When the user saved the post (unix timestamp converted)
        creator_username: Username of the post creator
    """

    url: str = Field(..., description="Instagram post URL")
    timestamp: datetime = Field(..., description="When the user saved the post")
    creator_username: str = Field(..., description="Username of the post creator")

    @computed_field
    @property
    def platform_id(self) -> str | None:
        """Extract shortcode from URL as platform identifier."""
        return extract_shortcode(self.url)

    @computed_field
    @property
    def media_hint(self) -> Literal["reel", "post", "igtv"]:
        """Infer media type from URL pattern."""
        return infer_media_hint(self.url)


class InstagramCollectionItemRef(BaseModel):
    """A single item within an Instagram collection.

    Attributes:
        url: Instagram post URL
        creator_username: Username of the post creator
        added_at: When the item was added to the collection
    """

    url: str = Field(..., description="Instagram post URL")
    creator_username: str = Field(..., description="Username of the post creator")
    added_at: datetime = Field(..., description="When added to the collection")

    @computed_field
    @property
    def platform_id(self) -> str | None:
        """Extract shortcode from URL as platform identifier."""
        return extract_shortcode(self.url)


class InstagramCollectionRef(BaseModel):
    """A user-created Instagram collection (saved folder).

    Attributes:
        name: Collection name as set by the user
        created_at: When the collection was created
        updated_at: When the collection was last updated
        items: List of items in this collection
    """

    name: str = Field(..., description="Collection name")
    created_at: datetime = Field(..., description="When the collection was created")
    updated_at: datetime = Field(..., description="When the collection was last updated")
    items: list[InstagramCollectionItemRef] = Field(default_factory=list)


class InstagramExportSummary(BaseModel):
    """Summary of parsed Instagram export for scope selection.

    Attributes:
        saved_count: Number of saved posts in the export
        collection_count: Number of user-created collections
        collection_names: Names of the collections found
    """

    saved_count: int = Field(..., ge=0, description="Number of saved posts")
    collection_count: int = Field(..., ge=0, description="Number of collections")
    collection_names: list[str] = Field(
        default_factory=list, description="Names of collections found"
    )


class InstagramParsedExport(BaseModel):
    """Complete parsed Instagram export data.

    Attributes:
        summary: Summary statistics of the parsed export
        saved_posts: List of saved post references
        collections: List of user-created collections with their items
    """

    summary: InstagramExportSummary
    saved_posts: list[InstagramPostReference] = Field(default_factory=list)
    collections: list[InstagramCollectionRef] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Exception classes — mirrors tiktok_export.py pattern
# ---------------------------------------------------------------------------


class InstagramParseError(Exception):
    """Base exception for Instagram parser errors."""

    code: str = "PARSE_ERROR"
    message: str = "An error occurred while parsing the Instagram export"

    def __init__(self, message: str | None = None, details: dict | None = None) -> None:
        self.message = message or self.__class__.message
        self.details = details or {}
        super().__init__(self.message)


class InvalidExportError(InstagramParseError):
    """Export structure doesn't match expected Instagram format."""

    code: str = "INVALID_EXPORT"
    message: str = "The uploaded file doesn't match the expected Instagram export format"


class EmptyExportError(InstagramParseError):
    """No saved posts found in the export."""

    code: str = "EMPTY_EXPORT"
    message: str = "No saved posts found in the Instagram export"


class ZipSecurityError(InstagramParseError):
    """ZIP file failed security checks."""

    code: str = "ZIP_SECURITY_ERROR"
    message: str = "The ZIP file failed security validation"
