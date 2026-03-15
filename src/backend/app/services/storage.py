"""Supabase Storage service for file operations.

This module provides a service for interacting with Supabase Storage,
including generating presigned URLs for direct uploads.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

# Storage bucket name for TikTok exports
BUCKET_NAME = "tiktok-exports"

# Presigned URL expiration time in seconds (1 hour)
PRESIGNED_URL_EXPIRY_SECONDS = 3600

# Maximum file size in bytes (500MB)
MAX_FILE_SIZE_BYTES = 524288000


@dataclass
class PresignedUrlResult:
    """Result of presigned URL generation.

    Attributes:
        success: Whether the operation succeeded
        presigned_url: The generated presigned URL (if success)
        error: Error message (if failed)
    """

    success: bool
    presigned_url: str | None = None
    error: str | None = None


class SupabaseStorageService:
    """Service for Supabase Storage operations.

    This service handles all interactions with Supabase Storage,
    including generating presigned URLs for uploads.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize the storage service.

        Args:
            settings: Application settings with Supabase credentials
        """
        self.settings = settings
        self.supabase_url = settings.supabase_url
        self.service_key = settings.supabase_secret_key

    def _get_storage_path(self, user_id: UUID, upload_id: UUID) -> str:
        """Generate the storage path for an upload.

        Storage path follows convention: {user_id}/{upload_id}.zip

        Args:
            user_id: The user's UUID
            upload_id: The upload's UUID

        Returns:
            Storage path string
        """
        return f"{user_id}/{upload_id}.zip"

    async def create_presigned_upload_url(
        self,
        user_id: UUID,
        upload_id: UUID,
    ) -> PresignedUrlResult:
        """Generate a presigned URL for uploading a file to storage.

        The presigned URL allows direct upload to Supabase Storage
        without proxying through the API server.

        Args:
            user_id: The user's UUID (for path)
            upload_id: The upload's UUID (for path)

        Returns:
            PresignedUrlResult with URL or error
        """
        storage_path = self._get_storage_path(user_id, upload_id)

        logger.info(
            {
                "event": "presigned_url_generation_started",
                "user_id": str(user_id),
                "upload_id": str(upload_id),
                "storage_path": storage_path,
            }
        )

        try:
            async with httpx.AsyncClient() as client:
                # Use Supabase Storage API to create presigned URL
                # POST /storage/v1/object/upload/sign/{bucket}/{path}
                url = (
                    f"{self.supabase_url}/storage/v1/object/upload/sign/"
                    f"{BUCKET_NAME}/{storage_path}"
                )

                headers = {
                    "Authorization": f"Bearer {self.service_key}",
                    "apikey": self.service_key,
                }

                response = await client.post(
                    url,
                    headers=headers,
                    timeout=30.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    # Supabase returns a token, we need to construct the full URL
                    signed_url = data.get("url") or data.get("signedURL")

                    if not signed_url:
                        logger.error(
                            {
                                "event": "presigned_url_generation_failed",
                                "user_id": str(user_id),
                                "upload_id": str(upload_id),
                                "reason": "no_url_in_response",
                                "response": data,
                            }
                        )
                        return PresignedUrlResult(
                            success=False,
                            error="Storage service returned invalid response",
                        )

                    # If the URL is relative, make it absolute
                    if signed_url.startswith("/"):
                        signed_url = f"{self.supabase_url}{signed_url}"

                    logger.info(
                        {
                            "event": "presigned_url_generated",
                            "user_id": str(user_id),
                            "upload_id": str(upload_id),
                            "storage_path": storage_path,
                        }
                    )

                    return PresignedUrlResult(
                        success=True,
                        presigned_url=signed_url,
                    )

                else:
                    logger.error(
                        {
                            "event": "presigned_url_generation_failed",
                            "user_id": str(user_id),
                            "upload_id": str(upload_id),
                            "status_code": response.status_code,
                            "response": response.text[:200] if response.text else None,
                        }
                    )
                    return PresignedUrlResult(
                        success=False,
                        error=f"Storage service returned status {response.status_code}",
                    )

        except httpx.TimeoutException:
            logger.error(
                {
                    "event": "presigned_url_generation_failed",
                    "user_id": str(user_id),
                    "upload_id": str(upload_id),
                    "reason": "timeout",
                }
            )
            return PresignedUrlResult(
                success=False,
                error="Storage service timed out",
            )

        except Exception as e:
            logger.error(
                {
                    "event": "presigned_url_generation_failed",
                    "user_id": str(user_id),
                    "upload_id": str(upload_id),
                    "reason": "exception",
                    "error": str(e),
                }
            )
            return PresignedUrlResult(
                success=False,
                error="Failed to connect to storage service",
            )

    def get_presigned_url_expiry(self) -> datetime:
        """Get the expiration time for a presigned URL.

        Returns:
            datetime when the URL expires (now + 1 hour)
        """
        return datetime.now(UTC) + timedelta(seconds=PRESIGNED_URL_EXPIRY_SECONDS)
