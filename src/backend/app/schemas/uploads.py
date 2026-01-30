"""Upload-related Pydantic schemas for API contracts.

This module defines request/response schemas for the upload API endpoints,
including presigned URL generation, upload record creation, and validation.
"""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class PresignedUrlRequest(BaseModel):
    """Request to generate a presigned upload URL.

    Attributes:
        filename: Original filename for reference (used for logging, not security)
        content_type: MIME type of the file (must be ZIP)
    """

    filename: str = Field(
        ...,
        description="Original filename for reference",
        max_length=255,
        min_length=1,
    )
    content_type: str = Field(
        default="application/zip",
        description="MIME type of the file",
    )


class PresignedUrlResponse(BaseModel):
    """Response containing the presigned URL and upload metadata.

    Attributes:
        upload_id: Unique identifier for this upload
        presigned_url: URL to upload file to (valid for 1 hour)
        storage_path: Path where file will be stored in bucket
        expires_at: When the presigned URL expires
        max_file_size: Maximum allowed file size in bytes (500MB)
    """

    upload_id: UUID = Field(..., description="Unique identifier for this upload")
    presigned_url: str = Field(..., description="URL to upload file to")
    storage_path: str = Field(..., description="Path in storage bucket")
    expires_at: datetime = Field(..., description="When the presigned URL expires")
    max_file_size: int = Field(..., description="Maximum allowed file size in bytes")


class UploadErrorCode:
    """Error codes for upload operations."""

    INVALID_CONTENT_TYPE = "INVALID_CONTENT_TYPE"
    UPLOAD_LIMIT_EXCEEDED = "UPLOAD_LIMIT_EXCEEDED"
    STORAGE_ERROR = "STORAGE_ERROR"


class UploadErrorResponse(BaseModel):
    """Error response for upload operations.

    Attributes:
        detail: Human-readable error message
        code: Machine-readable error code
    """

    detail: str = Field(..., description="Human-readable error message")
    code: str = Field(..., description="Machine-readable error code")


# ============================================================================
# Validation schemas (Task 2-2.5)
# ============================================================================


class ValidationErrorCode(str, Enum):
    """Error codes for validation failures."""

    INVALID_FILE = "INVALID_FILE"  # Not a valid ZIP
    INVALID_EXPORT = "INVALID_EXPORT"  # ZIP doesn't contain TikTok export
    EMPTY_EXPORT = "EMPTY_EXPORT"  # No liked/favorited videos
    FILE_TOO_LARGE = "FILE_TOO_LARGE"  # Exceeds 500MB
    FILE_CORRUPTED = "FILE_CORRUPTED"  # ZIP is corrupted
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"  # Not JSON format export


class ValidationResult(BaseModel):
    """Result of file validation.

    Attributes:
        valid: Whether the file passed validation
        error_code: Error code if validation failed
        error_message: Human-readable error message if validation failed
        liked_count: Number of liked videos found (if valid)
        favorited_count: Number of favorited videos found (if valid)
        file_hash: SHA256 hash for debugging (not content)
    """

    valid: bool = Field(..., description="Whether the file passed validation")
    error_code: ValidationErrorCode | None = Field(
        default=None,
        description="Error code if validation failed",
    )
    error_message: str | None = Field(
        default=None,
        description="Human-readable error message",
    )
    liked_count: int | None = Field(
        default=None,
        description="Number of liked videos found (if valid)",
    )
    favorited_count: int | None = Field(
        default=None,
        description="Number of favorited videos found (if valid)",
    )
    file_hash: str | None = Field(
        default=None,
        description="SHA256 hash for debugging (not content)",
    )


class ValidateUploadResponse(BaseModel):
    """Response from validation endpoint.

    Attributes:
        upload_id: The upload that was validated
        validation: The validation result
    """

    upload_id: UUID
    validation: ValidationResult
