"""Upload service for managing TikTok export uploads.

This module provides business logic for upload operations including:
- Presigned URL generation for direct uploads
- Scope selection for video processing
- Tier-based limit enforcement
- Upload state validation and transitions
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from app.config import Settings
from app.schemas.uploads import ScopeSelectionResponse, ScopeType
from app.services.storage import (
    BUCKET_NAME,
    MAX_FILE_SIZE_BYTES,
    SupabaseStorageService,
)
from app.services.tiers import (
    check_within_limit,
    estimate_processing_minutes,
    get_tier_limit,
)

logger = logging.getLogger(__name__)

# Allowed MIME types for TikTok exports
ALLOWED_CONTENT_TYPES = {
    "application/zip",
    "application/x-zip-compressed",
    "application/octet-stream",
}

# Upload limits per tier
# Free tier: 1 upload (one-time)
# Paid tiers: unlimited active uploads
TIER_UPLOAD_LIMITS: dict[str, int | None] = {
    "free": 1,
    "explorer": None,  # Unlimited
    "expert": None,  # Unlimited
    "pioneer": None,  # Unlimited
}

# Valid upload statuses that allow scope selection
SCOPE_SELECTABLE_STATUSES = frozenset({"validated", "scope_selected"})

# Statuses that indicate processing has started
PROCESSING_STATUSES = frozenset({"consented", "processing", "complete", "failed"})


@dataclass
class CreatePresignedUrlResult:
    """Result of presigned URL creation.

    Attributes:
        success: Whether the operation succeeded
        upload_id: Generated upload UUID (if success)
        presigned_url: The presigned URL for upload (if success)
        storage_path: Path in storage bucket (if success)
        expires_at: When the URL expires (if success)
        max_file_size: Maximum allowed file size (if success)
        error: Error message (if failed)
        error_code: Error code (if failed)
    """

    success: bool
    upload_id: UUID | None = None
    presigned_url: str | None = None
    storage_path: str | None = None
    expires_at: datetime | None = None
    max_file_size: int | None = None
    error: str | None = None
    error_code: str | None = None


@dataclass
class ScopeSelectionResult:
    """Result of scope selection operation.

    Attributes:
        success: Whether the operation succeeded
        response: The scope selection response (if successful)
        error_type: Type of error (if failed)
        error_message: Error message (if failed)
        error_details: Additional error details (if failed)
    """

    success: bool
    response: ScopeSelectionResponse | None = None
    error_type: Literal["not_validated", "already_processing", "tier_limit_exceeded"] | None = None
    error_message: str | None = None
    error_details: dict | None = None


class UploadService:
    """Service for managing TikTok export uploads.

    This service handles:
    - Presigned URL generation for direct uploads
    - Tier-based upload limit enforcement
    - Upload record management
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize the upload service.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.storage_service = SupabaseStorageService(settings)

    def _validate_content_type(self, content_type: str) -> bool:
        """Validate that the content type is allowed.

        Args:
            content_type: MIME type to validate

        Returns:
            True if content type is allowed, False otherwise
        """
        return content_type in ALLOWED_CONTENT_TYPES

    def _check_tier_upload_limit(
        self,
        user_tier: str,
        current_upload_count: int,
    ) -> bool:
        """Check if user has reached their tier's upload limit.

        Args:
            user_tier: User's subscription tier
            current_upload_count: Number of existing uploads

        Returns:
            True if user can upload, False if limit reached
        """
        limit = TIER_UPLOAD_LIMITS.get(user_tier, 1)

        # None means unlimited
        if limit is None:
            return True

        return current_upload_count < limit

    async def create_presigned_url(
        self,
        user_id: UUID,
        filename: str,
        content_type: str,
        user_tier: str = "free",
        current_upload_count: int = 0,
    ) -> CreatePresignedUrlResult:
        """Create a presigned URL for uploading a TikTok export.

        This method:
        1. Validates the content type
        2. Checks tier-based upload limits
        3. Generates a presigned URL from Supabase Storage
        4. Returns the URL and metadata

        Note: The caller is responsible for creating the upload record
        in the database after this method returns successfully.

        Args:
            user_id: The user's UUID
            filename: Original filename (for logging)
            content_type: MIME type of the file
            user_tier: User's subscription tier (for limit checking)
            current_upload_count: Number of existing non-failed uploads

        Returns:
            CreatePresignedUrlResult with URL or error
        """
        logger.info(
            {
                "event": "presigned_url_requested",
                "user_id": str(user_id),
                "user_tier": user_tier,
                "content_type": content_type,
            }
        )

        # Validate content type
        if not self._validate_content_type(content_type):
            logger.info(
                {
                    "event": "presigned_url_rejected",
                    "user_id": str(user_id),
                    "reason": "invalid_content_type",
                    "content_type": content_type,
                }
            )
            return CreatePresignedUrlResult(
                success=False,
                error=f"Invalid content type: {content_type}. Only ZIP files are accepted.",
                error_code="INVALID_CONTENT_TYPE",
            )

        # Check tier limits
        if not self._check_tier_upload_limit(user_tier, current_upload_count):
            logger.info(
                {
                    "event": "presigned_url_rejected",
                    "user_id": str(user_id),
                    "reason": "upload_limit_exceeded",
                    "user_tier": user_tier,
                    "current_upload_count": current_upload_count,
                }
            )
            return CreatePresignedUrlResult(
                success=False,
                error="Upload limit reached for your subscription tier",
                error_code="UPLOAD_LIMIT_EXCEEDED",
            )

        # Generate upload ID
        upload_id = uuid4()

        # Generate presigned URL
        url_result = await self.storage_service.create_presigned_upload_url(
            user_id=user_id,
            upload_id=upload_id,
        )

        if not url_result.success:
            logger.error(
                {
                    "event": "presigned_url_failed",
                    "user_id": str(user_id),
                    "upload_id": str(upload_id),
                    "error": url_result.error,
                }
            )
            return CreatePresignedUrlResult(
                success=False,
                error=url_result.error or "Failed to generate upload URL",
                error_code="STORAGE_ERROR",
            )

        # Get storage path and expiry
        storage_path = f"{BUCKET_NAME}/{user_id}/{upload_id}.zip"
        expires_at = self.storage_service.get_presigned_url_expiry()

        logger.info(
            {
                "event": "presigned_url_generated",
                "user_id": str(user_id),
                "upload_id": str(upload_id),
                "storage_path": storage_path,
                "expires_at": expires_at.isoformat(),
            }
        )

        return CreatePresignedUrlResult(
            success=True,
            upload_id=upload_id,
            presigned_url=url_result.presigned_url,
            storage_path=storage_path,
            expires_at=expires_at,
            max_file_size=MAX_FILE_SIZE_BYTES,
        )


class UploadsService:
    """Service for managing uploads and scope selection.

    This service handles:
    - Scope selection and validation
    - Tier limit enforcement
    - Upload state transitions
    """

    def __init__(self) -> None:
        """Initialize the uploads service."""
        pass

    def _calculate_scope_counts(
        self,
        scope: ScopeType,
        liked_count: int,
        favorited_count: int,
    ) -> tuple[int, int, int]:
        """Calculate item counts based on selected scope.

        Args:
            scope: The selected scope type
            liked_count: Total liked videos in export
            favorited_count: Total favorited videos in export

        Returns:
            Tuple of (total_items, liked_in_selection, favorited_in_selection)
        """
        if scope == ScopeType.LIKED:
            return liked_count, liked_count, 0
        elif scope == ScopeType.FAVORITED:
            return favorited_count, 0, favorited_count
        else:  # ScopeType.BOTH
            # Videos can be both liked and favorited, but we count unique videos
            # For simplicity, we assume no overlap (worst case for tier limits)
            # Actual deduplication happens during processing
            total = liked_count + favorited_count
            return total, liked_count, favorited_count

    def _validate_upload_status(
        self,
        upload_status: str,
    ) -> tuple[bool, str | None, str | None]:
        """Validate that upload is in a valid state for scope selection.

        Args:
            upload_status: Current upload status

        Returns:
            Tuple of (is_valid, error_type, error_message)
        """
        if upload_status in PROCESSING_STATUSES:
            msg = (
                f"Cannot change scope after processing has started. Current status: {upload_status}"
            )
            return (False, "already_processing", msg)

        if upload_status not in SCOPE_SELECTABLE_STATUSES:
            return (
                False,
                "not_validated",
                f"Upload must be validated before setting scope. Current status: {upload_status}",
            )

        return True, None, None

    async def select_scope(
        self,
        upload_id: UUID,
        user_id: UUID,
        scope: ScopeType,
        user_tier: str,
        upload_status: str,
        liked_count: int,
        favorited_count: int,
    ) -> ScopeSelectionResult:
        """Select the processing scope for an upload.

        This validates the scope selection against the user's tier limits
        and returns the selection details.

        Args:
            upload_id: The upload ID to update
            user_id: The user making the request
            scope: The desired scope (liked, favorited, or both)
            user_tier: The user's subscription tier
            upload_status: Current upload status
            liked_count: Number of liked videos in export
            favorited_count: Number of favorited videos in export

        Returns:
            ScopeSelectionResult with success status and response/error details
        """
        logger.info(
            {
                "event": "scope_selection_requested",
                "upload_id": str(upload_id),
                "user_id": str(user_id),
                "scope": scope.value,
                "user_tier": user_tier,
            }
        )

        # Validate upload status
        is_valid, error_type, error_message = self._validate_upload_status(upload_status)
        if not is_valid:
            logger.info(
                {
                    "event": "scope_selection_failed",
                    "upload_id": str(upload_id),
                    "reason": error_type,
                    "upload_status": upload_status,
                }
            )
            return ScopeSelectionResult(
                success=False,
                error_type=error_type,
                error_message=error_message,
            )

        # Calculate counts based on scope
        total_items, selected_liked, selected_favorited = self._calculate_scope_counts(
            scope, liked_count, favorited_count
        )

        # Get tier limit and check
        try:
            tier_limit = get_tier_limit(user_tier)
        except ValueError as e:
            logger.error(
                {
                    "event": "scope_selection_error",
                    "upload_id": str(upload_id),
                    "error": str(e),
                }
            )
            # Default to free tier if unknown
            tier_limit = get_tier_limit("free")

        within_limit = check_within_limit(user_tier, total_items)

        if not within_limit:
            logger.info(
                {
                    "event": "scope_selection_tier_exceeded",
                    "upload_id": str(upload_id),
                    "total_items": total_items,
                    "tier_limit": tier_limit,
                    "tier": user_tier,
                }
            )
            error_msg = (
                f"Selection of {total_items} videos exceeds your {user_tier} "
                f"tier limit of {tier_limit}"
            )
            return ScopeSelectionResult(
                success=False,
                error_type="tier_limit_exceeded",
                error_message=error_msg,
                error_details={
                    "selected_count": total_items,
                    "tier_limit": tier_limit,
                    "tier": user_tier,
                    "upgrade_required": True,
                },
            )

        # Calculate processing time estimate
        estimated_minutes = estimate_processing_minutes(total_items)

        # Build successful response
        response = ScopeSelectionResponse(
            upload_id=upload_id,
            scope=scope,
            total_items=total_items,
            liked_count=selected_liked,
            favorited_count=selected_favorited,
            tier_limit=tier_limit,
            within_limit=within_limit,
            estimated_processing_minutes=estimated_minutes,
            ready_for_consent=True,
        )

        logger.info(
            {
                "event": "scope_selection_success",
                "upload_id": str(upload_id),
                "scope": scope.value,
                "total_items": total_items,
                "tier": user_tier,
                "within_limit": within_limit,
                "estimated_minutes": estimated_minutes,
            }
        )

        return ScopeSelectionResult(
            success=True,
            response=response,
        )
