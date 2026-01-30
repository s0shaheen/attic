"""TikTok export data models.

This module defines Pydantic models for parsing TikTok data export files.
These models represent the structure of parsed export data and error types.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TikTokVideoReference(BaseModel):
    """A single video reference from the TikTok export.

    Attributes:
        url: TikTok video URL (e.g., https://www.tiktokv.com/share/video/123/)
        timestamp: When the user interacted with the video
        interaction_type: Type of interaction ('liked' or 'favorited')
    """

    url: str = Field(..., description="TikTok video URL")
    timestamp: datetime = Field(..., description="When the user interacted with the video")
    interaction_type: Literal["liked", "favorited"] = Field(..., description="Type of interaction")


class TikTokExportSummary(BaseModel):
    """Summary of parsed export for scope selection.

    Attributes:
        liked_count: Number of liked videos in the export
        favorited_count: Number of favorited videos in the export
        total_count: Total unique videos across both lists
        has_liked: Whether the export contains liked videos
        has_favorited: Whether the export contains favorited videos
    """

    liked_count: int = Field(..., ge=0, description="Number of liked videos")
    favorited_count: int = Field(..., ge=0, description="Number of favorited videos")
    total_count: int = Field(..., ge=0, description="Total unique videos")
    has_liked: bool = Field(..., description="Export contains liked videos")
    has_favorited: bool = Field(..., description="Export contains favorited videos")


class TikTokParsedExport(BaseModel):
    """Complete parsed export data.

    Contains both the summary and the full lists of video references.

    Attributes:
        summary: Summary statistics of the parsed export
        liked_videos: List of liked video references
        favorited_videos: List of favorited video references
    """

    summary: TikTokExportSummary
    liked_videos: list[TikTokVideoReference] = Field(default_factory=list)
    favorited_videos: list[TikTokVideoReference] = Field(default_factory=list)


class ParseError(BaseModel):
    """Structured parse error for API responses.

    Attributes:
        code: Machine-readable error code
        message: Human-readable error message
        details: Additional context about the error
    """

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict | None = Field(default=None, description="Additional context")


# Exception classes for parser errors


class TikTokParseError(Exception):
    """Base exception for TikTok parser errors.

    All parser exceptions inherit from this class, allowing callers
    to catch all parser-related errors with a single except clause.

    Attributes:
        code: Machine-readable error code
        message: Human-readable error description
    """

    code: str = "PARSE_ERROR"
    message: str = "An error occurred while parsing the TikTok export"

    def __init__(self, message: str | None = None, details: dict | None = None) -> None:
        """Initialize the parse error.

        Args:
            message: Optional custom error message
            details: Optional additional context about the error
        """
        self.message = message or self.__class__.message
        self.details = details or {}
        super().__init__(self.message)

    def to_parse_error(self) -> ParseError:
        """Convert to a ParseError model for API responses.

        Returns:
            ParseError model with code, message, and details
        """
        return ParseError(
            code=self.code,
            message=self.message,
            details=self.details if self.details else None,
        )


class InvalidExportError(TikTokParseError):
    """Export structure doesn't match expected TikTok format.

    Raised when the ZIP file doesn't contain the expected directory structure
    or the JSON files don't match the expected TikTok export format.
    """

    code: str = "INVALID_EXPORT"
    message: str = "The uploaded file doesn't match the expected TikTok export format"


class EmptyExportError(TikTokParseError):
    """No videos found in the specified scope.

    Raised when the parser completes successfully but finds no videos
    in the requested scope (liked, favorited, or both).
    """

    code: str = "EMPTY_EXPORT"
    message: str = "No videos found in the specified scope"


class ZipSecurityError(TikTokParseError):
    """ZIP file failed security checks.

    Raised when the ZIP file contains potentially malicious content,
    such as path traversal attempts (zip-slip), absolute paths,
    or symbolic links.
    """

    code: str = "ZIP_SECURITY_ERROR"
    message: str = "The ZIP file failed security validation"
