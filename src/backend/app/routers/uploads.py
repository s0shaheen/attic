"""Upload management routes.

This module contains endpoints for managing TikTok export uploads,
including presigned URL generation for direct-to-storage uploads.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user
from app.core.config import Settings, get_settings
from app.models.auth import AuthenticatedUser
from app.schemas.uploads import (
    PresignedUrlRequest,
    PresignedUrlResponse,
    UploadErrorCode,
    UploadErrorResponse,
)
from app.services.uploads import UploadService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


@router.post(
    "/presigned-url",
    response_model=PresignedUrlResponse,
    status_code=200,
    responses={
        200: {"description": "Presigned URL generated successfully"},
        400: {
            "description": "Invalid content type",
            "model": UploadErrorResponse,
        },
        401: {"description": "Not authenticated"},
        403: {
            "description": "Upload limit exceeded for tier",
            "model": UploadErrorResponse,
        },
        500: {
            "description": "Failed to generate presigned URL",
            "model": UploadErrorResponse,
        },
    },
)
async def create_presigned_url(
    request: PresignedUrlRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PresignedUrlResponse:
    """Generate a presigned URL for uploading a TikTok export.

    This endpoint creates a presigned URL that allows the client to upload
    a TikTok export ZIP file directly to Supabase Storage. The URL is valid
    for 1 hour.

    The endpoint also creates a pending upload record in the database to
    track the upload status.

    Note: Currently, tier limits and upload counts are not enforced via
    database queries. This is a placeholder for when the database layer
    is fully integrated. Free tier users are assumed to have 0 existing
    uploads (can always upload).

    Args:
        request: Presigned URL request with filename and content type
        user: Authenticated user from JWT
        settings: Application settings

    Returns:
        PresignedUrlResponse with presigned URL and upload metadata

    Raises:
        HTTPException: 400 if content type invalid, 401 if not authenticated,
                      403 if upload limit exceeded, 500 if storage error
    """
    upload_service = UploadService(settings)

    # TODO: Query database for user's tier and existing upload count
    # For now, use default values:
    # - All users are treated as free tier
    # - Existing upload count is 0 (allows first upload)
    #
    # This will be implemented when database integration is complete:
    # 1. Query users table for subscription_tier
    # 2. Query uploads table for count where user_id = user.id
    #    and status NOT IN ('failed')
    user_tier = "free"
    current_upload_count = 0

    result = await upload_service.create_presigned_url(
        user_id=user.id,
        filename=request.filename,
        content_type=request.content_type,
        user_tier=user_tier,
        current_upload_count=current_upload_count,
    )

    if not result.success:
        # Map error codes to HTTP status codes
        if result.error_code == UploadErrorCode.INVALID_CONTENT_TYPE:
            raise HTTPException(
                status_code=400,
                detail=UploadErrorResponse(
                    detail=result.error or "Invalid content type",
                    code=result.error_code,
                ).model_dump(),
            )
        elif result.error_code == UploadErrorCode.UPLOAD_LIMIT_EXCEEDED:
            raise HTTPException(
                status_code=403,
                detail=UploadErrorResponse(
                    detail=result.error or "Upload limit exceeded",
                    code=result.error_code,
                ).model_dump(),
            )
        else:
            # Storage error or unknown error
            logger.error(
                {
                    "event": "presigned_url_endpoint_failed",
                    "user_id": str(user.id),
                    "error": result.error,
                    "error_code": result.error_code,
                }
            )
            raise HTTPException(
                status_code=500,
                detail=UploadErrorResponse(
                    detail=result.error or "Failed to generate upload URL",
                    code=result.error_code or UploadErrorCode.STORAGE_ERROR,
                ).model_dump(),
            )

    # TODO: Create upload record in database with pending status
    # This will be implemented when database integration is complete:
    # upload_record = Upload(
    #     id=result.upload_id,
    #     user_id=user.id,
    #     source_platform="tiktok",
    #     scope=None,  # Set later via scope selection
    #     status="pending",
    #     storage_path=result.storage_path,
    #     original_filename=request.filename,
    # )
    # await db.add(upload_record)
    # await db.commit()

    return PresignedUrlResponse(
        upload_id=result.upload_id,  # type: ignore[arg-type]
        presigned_url=result.presigned_url,  # type: ignore[arg-type]
        storage_path=result.storage_path,  # type: ignore[arg-type]
        expires_at=result.expires_at,  # type: ignore[arg-type]
        max_file_size=result.max_file_size,  # type: ignore[arg-type]
    )
