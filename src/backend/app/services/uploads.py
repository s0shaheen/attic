"""Upload service for managing TikTok export uploads.

This module provides business logic for upload operations,
including presigned URL generation and tier-based limit enforcement.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from app.core.config import Settings
from app.services.storage import (
    BUCKET_NAME,
    MAX_FILE_SIZE_BYTES,
    SupabaseStorageService,
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
