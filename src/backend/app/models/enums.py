"""Shared enums for Attic models."""

from enum import StrEnum


class MediaType(StrEnum):
    """Media type classification for content processing.

    Used to determine pipeline branching and processing requirements.
    String-based to avoid ALTER TYPE complexity when adding values.
    """

    VIDEO = "video"  # Standard video with audio
    IMAGE = "image"  # Single static image
    SLIDESHOW = "slideshow"  # Multiple images (TikTok photo mode)
