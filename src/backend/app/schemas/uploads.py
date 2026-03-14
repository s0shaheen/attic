"""Upload-related Pydantic schemas for API contracts.

This module defines request/response schemas for the upload API endpoints,
including presigned URL generation, upload record creation, and validation.
"""

from datetime import datetime
from enum import StrEnum
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


class ValidationErrorCode(StrEnum):
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


# ============================================================================
# Scope selection schemas (Task 2-2.6)
# ============================================================================


class ScopeType(StrEnum):
    """Scope options for video processing.

    Determines which videos from the TikTok export to process.
    """

    LIKED = "liked"
    FAVORITED = "favorited"
    BOTH = "both"


class ScopeSelectionRequest(BaseModel):
    """Request to set the processing scope.

    Attributes:
        scope: Which videos to process (liked, favorited, or both)
    """

    scope: ScopeType = Field(..., description="Which videos to process")


class ScopeSelectionResponse(BaseModel):
    """Response after scope selection.

    Attributes:
        upload_id: The upload ID that was updated
        scope: The selected scope
        total_items: Number of items to process based on scope
        liked_count: Liked videos included in selection
        favorited_count: Favorited videos included in selection
        tier_limit: User's tier video limit
        within_limit: Whether selection fits within tier limit
        estimated_processing_minutes: Estimated time to complete processing
        ready_for_consent: Whether upload is ready for consent capture
    """

    upload_id: UUID
    scope: ScopeType
    total_items: int = Field(..., description="Number of items to process")
    liked_count: int = Field(..., description="Liked videos in selection")
    favorited_count: int = Field(..., description="Favorited videos in selection")
    tier_limit: int = Field(..., description="User's tier video limit")
    within_limit: bool = Field(..., description="Selection fits within tier limit")
    estimated_processing_minutes: int = Field(
        ..., description="Estimated time to complete processing"
    )
    ready_for_consent: bool = Field(..., description="Whether upload is ready for consent capture")


class TierLimitExceededError(BaseModel):
    """Error response when scope exceeds tier limit.

    Attributes:
        error: Error code
        message: Human-readable error message
        selected_count: Number of items selected
        tier_limit: User's tier limit
        tier: User's current subscription tier
        upgrade_required: Whether upgrade is needed to process this selection
    """

    error: str = Field(default="TIER_LIMIT_EXCEEDED")
    message: str
    selected_count: int
    tier_limit: int
    tier: str
    upgrade_required: bool = Field(default=True)


# ============================================================================
# Consent schemas (Task 2-2.7)
# ============================================================================

# Current consent text version - increment when text changes
CURRENT_CONSENT_VERSION = "1.0.0"


class ConsentRequest(BaseModel):
    """Request to record consent for data processing.

    Attributes:
        consent_given: User explicitly consented
        consent_version: Version of consent text shown
    """

    consent_given: bool = Field(
        ...,
        description="User explicitly consented to data processing",
    )
    consent_version: str = Field(
        default=CURRENT_CONSENT_VERSION,
        description="Version of consent text shown to user",
        max_length=20,
    )


class ConsentResponse(BaseModel):
    """Response after consent is recorded.

    Attributes:
        upload_id: The upload ID that was updated
        consent_given: Whether consent was given
        consent_version: Version of consent text recorded
        consent_at: Timestamp when consent was recorded
        ready_to_process: Whether processing can now start
    """

    upload_id: UUID
    consent_given: bool = Field(..., description="Whether consent was given")
    consent_version: str = Field(..., description="Version of consent text recorded")
    consent_at: datetime = Field(..., description="Timestamp when consent was recorded")
    ready_to_process: bool = Field(..., description="Whether processing can now start")
