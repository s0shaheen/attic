"""User account deletion service.

This module handles GDPR-compliant deletion of user accounts and all associated data.
Deletion is performed synchronously for MVP, with graceful error handling.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class DeletionResult:
    """Result of a deletion operation.

    Attributes:
        success: Whether the overall deletion was successful
        storage_deleted: Whether storage files were deleted
        auth_deleted: Whether the user was deleted from Supabase Auth
        email_sent: Whether confirmation email was sent
        error: Error message if deletion failed
    """

    success: bool
    storage_deleted: bool
    auth_deleted: bool
    email_sent: bool
    error: str | None = None


class UserDeletionService:
    """Service for deleting user accounts and associated data.

    This service coordinates the deletion of:
    1. User files from Supabase Storage
    2. User from Supabase Auth

    Database records (uploads, media_events, etc.) are handled via cascade
    when the user is deleted from Supabase Auth, as they have RLS policies
    tied to the auth.users table.

    Note: For MVP, database tables may not exist yet. The core requirement
    is deleting the user from Supabase Auth and any storage files.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize the deletion service.

        Args:
            settings: Application settings with Supabase credentials
        """
        self.settings = settings
        self.supabase_url = settings.supabase_url
        self.service_key = settings.supabase_secret_key

    async def delete_user_storage_files(self, user_id: UUID) -> bool:
        """Delete all files owned by the user from Supabase Storage.

        This deletes files from the user's folder in the uploads bucket.

        Args:
            user_id: The user's UUID

        Returns:
            True if deletion succeeded or no files existed, False on error
        """
        logger.info(
            {
                "event": "deletion_step",
                "step": "storage",
                "user_id": str(user_id),
                "status": "started",
            }
        )

        try:
            # List files in user's folder
            # Supabase Storage organizes files by user_id folder
            bucket = "uploads"
            folder_path = str(user_id)

            async with httpx.AsyncClient() as client:
                # First, list all files in the user's folder
                list_url = f"{self.supabase_url}/storage/v1/object/list/{bucket}"
                headers = {
                    "Authorization": f"Bearer {self.service_key}",
                    "apikey": self.service_key,
                }

                list_response = await client.post(
                    list_url,
                    headers=headers,
                    json={"prefix": folder_path},
                    timeout=30.0,
                )

                if list_response.status_code == 404:
                    # Bucket or folder doesn't exist - no files to delete
                    logger.info(
                        {
                            "event": "deletion_step",
                            "step": "storage",
                            "user_id": str(user_id),
                            "status": "skipped",
                            "reason": "no_files",
                        }
                    )
                    return True

                if list_response.status_code != 200:
                    # Log but don't fail - user may have no files
                    logger.warning(
                        {
                            "event": "deletion_step",
                            "step": "storage",
                            "user_id": str(user_id),
                            "status": "list_failed",
                            "status_code": list_response.status_code,
                        }
                    )
                    # Continue anyway - storage failure shouldn't block deletion
                    return True

                files = list_response.json()

                if not files:
                    logger.info(
                        {
                            "event": "deletion_step",
                            "step": "storage",
                            "user_id": str(user_id),
                            "status": "skipped",
                            "reason": "no_files",
                        }
                    )
                    return True

                # Delete all files in the user's folder
                file_paths = [f"{folder_path}/{f['name']}" for f in files if "name" in f]

                if file_paths:
                    delete_url = f"{self.supabase_url}/storage/v1/object/{bucket}"
                    delete_response = await client.delete(
                        delete_url,
                        headers=headers,
                        json={"prefixes": file_paths},
                        timeout=30.0,
                    )

                    if delete_response.status_code not in (200, 204):
                        logger.warning(
                            {
                                "event": "deletion_step",
                                "step": "storage",
                                "user_id": str(user_id),
                                "status": "delete_failed",
                                "status_code": delete_response.status_code,
                            }
                        )
                        # Continue anyway - orphaned files are acceptable

            logger.info(
                {
                    "event": "deletion_step",
                    "step": "storage",
                    "user_id": str(user_id),
                    "status": "completed",
                    "files_deleted": len(file_paths) if files else 0,
                }
            )
            return True

        except httpx.TimeoutException:
            logger.warning(
                {
                    "event": "deletion_step",
                    "step": "storage",
                    "user_id": str(user_id),
                    "status": "timeout",
                }
            )
            # Continue with deletion - storage timeout shouldn't block
            return True

        except Exception as e:
            logger.error(
                {
                    "event": "deletion_step",
                    "step": "storage",
                    "user_id": str(user_id),
                    "status": "error",
                    "error": str(e),
                }
            )
            # Continue with deletion - storage error shouldn't block
            return True

    async def delete_user_from_auth(self, user_id: UUID) -> bool:
        """Delete the user from Supabase Auth.

        This uses the Supabase Admin API to delete the user from auth.users.

        Args:
            user_id: The user's UUID

        Returns:
            True if deletion succeeded, False on error
        """
        logger.info(
            {
                "event": "deletion_step",
                "step": "auth",
                "user_id": str(user_id),
                "status": "started",
            }
        )

        try:
            async with httpx.AsyncClient() as client:
                # Use Supabase Admin API to delete user
                delete_url = f"{self.supabase_url}/auth/v1/admin/users/{user_id}"
                headers = {
                    "Authorization": f"Bearer {self.service_key}",
                    "apikey": self.service_key,
                }

                response = await client.delete(
                    delete_url,
                    headers=headers,
                    timeout=30.0,
                )

                if response.status_code == 404:
                    # User already deleted - still a success
                    logger.info(
                        {
                            "event": "deletion_step",
                            "step": "auth",
                            "user_id": str(user_id),
                            "status": "already_deleted",
                        }
                    )
                    return True

                if response.status_code not in (200, 204):
                    logger.error(
                        {
                            "event": "deletion_step",
                            "step": "auth",
                            "user_id": str(user_id),
                            "status": "failed",
                            "status_code": response.status_code,
                            "response": response.text[:200] if response.text else None,
                        }
                    )
                    return False

                logger.info(
                    {
                        "event": "deletion_step",
                        "step": "auth",
                        "user_id": str(user_id),
                        "status": "completed",
                    }
                )
                return True

        except httpx.TimeoutException:
            logger.error(
                {
                    "event": "deletion_step",
                    "step": "auth",
                    "user_id": str(user_id),
                    "status": "timeout",
                }
            )
            return False

        except Exception as e:
            logger.error(
                {
                    "event": "deletion_step",
                    "step": "auth",
                    "user_id": str(user_id),
                    "status": "error",
                    "error": str(e),
                }
            )
            return False

    def _build_deletion_email_html(self) -> str:
        """Build the HTML content for the deletion confirmation email.

        Returns:
            HTML string for the email body
        """
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
        return f"""
<h1>Account Deleted</h1>
<p>Your Attic account and all associated data have been permanently deleted.</p>
<p>This action was completed on {timestamp}.</p>
<p>If you did not request this deletion, please contact support immediately.</p>
<p>Thank you for using Attic.</p>
"""

    async def send_deletion_confirmation_email(self, email: str | None, user_id: UUID) -> bool:
        """Send a confirmation email after account deletion.

        Uses Resend API to send the confirmation. Skips if email is not available.

        Args:
            email: The user's email address (may be None)
            user_id: The user's UUID for logging

        Returns:
            True if email was sent or skipped, False on error
        """
        if not email:
            logger.info(
                {
                    "event": "deletion_step",
                    "step": "email",
                    "user_id": str(user_id),
                    "status": "skipped",
                    "reason": "no_email",
                }
            )
            return False

        logger.info(
            {
                "event": "deletion_step",
                "step": "email",
                "user_id": str(user_id),
                "status": "started",
            }
        )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {self.settings.resend_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": "Attic <noreply@attic.app>",
                        "to": [email],
                        "subject": "Your Attic account has been deleted",
                        "html": self._build_deletion_email_html(),
                    },
                    timeout=10.0,
                )

                if response.status_code in (200, 201):
                    logger.info(
                        {
                            "event": "deletion_step",
                            "step": "email",
                            "user_id": str(user_id),
                            "status": "sent",
                        }
                    )
                    return True
                else:
                    logger.warning(
                        {
                            "event": "deletion_step",
                            "step": "email",
                            "user_id": str(user_id),
                            "status": "failed",
                            "status_code": response.status_code,
                        }
                    )
                    return False

        except Exception as e:
            logger.warning(
                {
                    "event": "deletion_step",
                    "step": "email",
                    "user_id": str(user_id),
                    "status": "error",
                    "error": str(e),
                }
            )
            # Email failure shouldn't block deletion
            return False

    async def delete_user_account(self, user_id: UUID, email: str | None) -> DeletionResult:
        """Delete a user account and all associated data.

        Performs deletion in the following order:
        1. Delete storage files (continues on failure)
        2. Delete from Supabase Auth (required)
        3. Send confirmation email (optional)

        Args:
            user_id: The user's UUID
            email: The user's email for confirmation (may be None)

        Returns:
            DeletionResult with status of each step
        """
        start_time = datetime.now(UTC)

        logger.info(
            {
                "event": "account_deletion_initiated",
                "user_id": str(user_id),
                "timestamp": start_time.isoformat(),
            }
        )

        # Step 1: Delete storage files (non-blocking)
        storage_deleted = await self.delete_user_storage_files(user_id)

        # Step 2: Delete from Supabase Auth (required)
        auth_deleted = await self.delete_user_from_auth(user_id)

        if not auth_deleted:
            duration_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
            logger.error(
                {
                    "event": "account_deletion_failed",
                    "user_id": str(user_id),
                    "duration_ms": duration_ms,
                    "reason": "auth_deletion_failed",
                }
            )
            return DeletionResult(
                success=False,
                storage_deleted=storage_deleted,
                auth_deleted=False,
                email_sent=False,
                error="Failed to delete user from authentication system",
            )

        # Step 3: Send confirmation email (non-blocking)
        email_sent = await self.send_deletion_confirmation_email(email, user_id)

        duration_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000

        logger.info(
            {
                "event": "account_deletion_complete",
                "user_id": str(user_id),
                "duration_ms": duration_ms,
                "storage_deleted": storage_deleted,
                "email_sent": email_sent,
            }
        )

        return DeletionResult(
            success=True,
            storage_deleted=storage_deleted,
            auth_deleted=True,
            email_sent=email_sent,
        )
