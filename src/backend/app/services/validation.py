"""Upload validation service.

This module provides validation for TikTok export uploads, including:
- ZIP file format validation
- TikTok export structure validation
- Content extraction for video counts

Security features:
- All validation runs in memory (no temp files on disk)
- Memory limits for ZIP extraction
- Timeout protection (caller should enforce)
- Hash generation for debugging (not content)
"""

import hashlib
import io
import logging
import zipfile
from dataclasses import dataclass
from typing import IO
from uuid import UUID

from app.schemas.tiktok_export import (
    EmptyExportError,
    InvalidExportError,
    TikTokParseError,
    ZipSecurityError,
)
from app.schemas.uploads import ValidationErrorCode, ValidationResult
from app.services.tiktok_parser import get_export_summary

logger = logging.getLogger(__name__)


@dataclass
class ValidationServiceResult:
    """Result from the validation service.

    Attributes:
        result: The validation result to return to client
        should_update_status: Whether to update the upload status in DB
        new_status: The new status to set if should_update_status is True
    """

    result: ValidationResult
    should_update_status: bool
    new_status: str | None


class ValidationService:
    """Service for validating TikTok export uploads.

    This service handles all validation logic for uploaded files:
    1. Validates file is a valid ZIP
    2. Validates ZIP contains TikTok export structure
    3. Extracts video counts for scope selection

    Usage:
        service = ValidationService()
        result = await service.validate_upload(file_content)
    """

    def __init__(self) -> None:
        """Initialize the validation service."""
        pass

    def _compute_file_hash(self, file_content: bytes) -> str:
        """Compute SHA256 hash of file content.

        Args:
            file_content: Raw file bytes

        Returns:
            Hex-encoded SHA256 hash
        """
        return hashlib.sha256(file_content).hexdigest()

    def _is_valid_zip(self, file_content: bytes) -> bool:
        """Check if the content is a valid ZIP file.

        Args:
            file_content: Raw file bytes

        Returns:
            True if valid ZIP, False otherwise
        """
        try:
            with zipfile.ZipFile(io.BytesIO(file_content), "r") as zf:
                # Try to read the file list to verify it's not corrupted
                zf.namelist()
            return True
        except zipfile.BadZipFile:
            return False
        except Exception:
            return False

    def _is_corrupted_zip(self, file_content: bytes) -> bool:
        """Check if the ZIP file is corrupted.

        A corrupted ZIP can be opened but fails CRC checks or has bad entries.

        Args:
            file_content: Raw file bytes

        Returns:
            True if corrupted, False if healthy
        """
        try:
            with zipfile.ZipFile(io.BytesIO(file_content), "r") as zf:
                # Test all entries for corruption
                result = zf.testzip()
                return result is not None  # Returns first bad file or None if OK
        except zipfile.BadZipFile:
            return True
        except Exception:
            return True

    async def validate_upload(
        self,
        upload_id: UUID,
        user_id: UUID,
        file_content: bytes,
    ) -> ValidationServiceResult:
        """Validate an uploaded TikTok export file.

        Performs comprehensive validation:
        1. Check file is a valid ZIP
        2. Check ZIP is not corrupted
        3. Validate TikTok export structure
        4. Extract video counts

        Args:
            upload_id: The upload ID being validated
            user_id: The user who owns the upload
            file_content: Raw bytes of the uploaded file

        Returns:
            ValidationServiceResult with validation outcome
        """
        logger.info(
            {
                "event": "validation_started",
                "upload_id": str(upload_id),
                "user_id": str(user_id),
                "file_size_bytes": len(file_content),
            }
        )

        # Compute file hash for debugging
        file_hash = self._compute_file_hash(file_content)

        # Check if it's a valid ZIP file
        if not self._is_valid_zip(file_content):
            logger.info(
                {
                    "event": "validation_failed",
                    "upload_id": str(upload_id),
                    "reason": "invalid_zip",
                    "file_hash": file_hash,
                }
            )
            return ValidationServiceResult(
                result=ValidationResult(
                    valid=False,
                    error_code=ValidationErrorCode.INVALID_FILE,
                    error_message="The uploaded file is not a valid ZIP archive",
                    file_hash=file_hash,
                ),
                should_update_status=True,
                new_status="invalid",
            )

        # Check if ZIP is corrupted
        if self._is_corrupted_zip(file_content):
            logger.info(
                {
                    "event": "validation_failed",
                    "upload_id": str(upload_id),
                    "reason": "corrupted_zip",
                    "file_hash": file_hash,
                }
            )
            return ValidationServiceResult(
                result=ValidationResult(
                    valid=False,
                    error_code=ValidationErrorCode.FILE_CORRUPTED,
                    error_message=(
                        "The ZIP file appears to be corrupted. "
                        "Please re-download your export from TikTok."
                    ),
                    file_hash=file_hash,
                ),
                should_update_status=True,
                new_status="invalid",
            )

        # Try to parse the TikTok export
        try:
            file_io: IO[bytes] = io.BytesIO(file_content)
            summary = get_export_summary(file_io)

            logger.info(
                {
                    "event": "validation_passed",
                    "upload_id": str(upload_id),
                    "liked_count": summary.liked_count,
                    "favorited_count": summary.favorited_count,
                    "file_hash": file_hash,
                }
            )

            return ValidationServiceResult(
                result=ValidationResult(
                    valid=True,
                    liked_count=summary.liked_count,
                    favorited_count=summary.favorited_count,
                    file_hash=file_hash,
                ),
                should_update_status=True,
                new_status="validated",
            )

        except InvalidExportError as e:
            logger.info(
                {
                    "event": "validation_failed",
                    "upload_id": str(upload_id),
                    "reason": "invalid_export",
                    "error": e.message,
                    "file_hash": file_hash,
                }
            )

            # Check if it's a format issue (TXT instead of JSON)
            error_code = ValidationErrorCode.INVALID_EXPORT
            error_message = (
                "This ZIP file doesn't contain a TikTok data export. "
                "Make sure you're uploading the file from TikTok's 'Download your data' feature."
            )

            # Check for unsupported format hint
            details = e.details or {}
            if details.get("reason") == "json_decode_error":
                error_code = ValidationErrorCode.UNSUPPORTED_FORMAT
                error_message = (
                    "Please make sure you selected 'JSON' format when "
                    "requesting your TikTok data export."
                )

            return ValidationServiceResult(
                result=ValidationResult(
                    valid=False,
                    error_code=error_code,
                    error_message=error_message,
                    file_hash=file_hash,
                ),
                should_update_status=True,
                new_status="invalid",
            )

        except EmptyExportError as e:
            logger.info(
                {
                    "event": "validation_failed",
                    "upload_id": str(upload_id),
                    "reason": "empty_export",
                    "error": e.message,
                    "file_hash": file_hash,
                }
            )

            return ValidationServiceResult(
                result=ValidationResult(
                    valid=False,
                    error_code=ValidationErrorCode.EMPTY_EXPORT,
                    error_message=(
                        "Your export doesn't contain any liked or favorited videos. "
                        "Make sure you have liked or favorited videos on TikTok."
                    ),
                    file_hash=file_hash,
                ),
                should_update_status=True,
                new_status="invalid",
            )

        except ZipSecurityError as e:
            logger.warning(
                {
                    "event": "validation_security_error",
                    "upload_id": str(upload_id),
                    "user_id": str(user_id),
                    "error": e.message,
                    "file_hash": file_hash,
                }
            )

            # Don't expose security details to user
            return ValidationServiceResult(
                result=ValidationResult(
                    valid=False,
                    error_code=ValidationErrorCode.FILE_CORRUPTED,
                    error_message=(
                        "The ZIP file appears to be corrupted or invalid. "
                        "Please re-download your export from TikTok."
                    ),
                    file_hash=file_hash,
                ),
                should_update_status=True,
                new_status="invalid",
            )

        except TikTokParseError as e:
            logger.error(
                {
                    "event": "validation_unexpected_error",
                    "upload_id": str(upload_id),
                    "error": e.message,
                    "error_code": e.code,
                    "file_hash": file_hash,
                }
            )

            return ValidationServiceResult(
                result=ValidationResult(
                    valid=False,
                    error_code=ValidationErrorCode.INVALID_EXPORT,
                    error_message="Failed to validate the export file. Please try again.",
                    file_hash=file_hash,
                ),
                should_update_status=True,
                new_status="invalid",
            )

        except Exception as e:
            logger.exception(
                {
                    "event": "validation_exception",
                    "upload_id": str(upload_id),
                    "error": str(e),
                    "file_hash": file_hash,
                }
            )

            return ValidationServiceResult(
                result=ValidationResult(
                    valid=False,
                    error_code=ValidationErrorCode.INVALID_FILE,
                    error_message=(
                        "An unexpected error occurred during validation. Please try again."
                    ),
                    file_hash=file_hash,
                ),
                should_update_status=False,
                new_status=None,
            )
