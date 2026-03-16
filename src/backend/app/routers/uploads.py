"""Upload management routes.

This module contains endpoints for managing TikTok export uploads,
including presigned URL generation for direct-to-storage uploads,
validation of uploaded files, scope selection, and consent capture.
"""

import json
import logging
from typing import Annotated
from uuid import UUID

import boto3
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.core.config import Settings, get_settings
from app.models.auth import AuthenticatedUser
from app.schemas.uploads import (
    ConsentRequest,
    ConsentResponse,
    PresignedUrlRequest,
    PresignedUrlResponse,
    ScopeSelectionRequest,
    ScopeSelectionResponse,
    TierLimitExceededError,
    UploadErrorCode,
    UploadErrorResponse,
    ValidateUploadResponse,
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


@router.post(
    "/{upload_id}/validate",
    response_model=ValidateUploadResponse,
    status_code=200,
    responses={
        200: {"description": "Validation complete (check valid field for result)"},
        401: {"description": "Not authenticated"},
        403: {"description": "Upload belongs to different user"},
        404: {"description": "Upload not found"},
        500: {"description": "Validation failed unexpectedly"},
    },
)
async def validate_upload(
    upload_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ValidateUploadResponse:
    """Validate an uploaded TikTok export file.

    This endpoint validates that the uploaded file:
    1. Is a valid ZIP file
    2. Contains a TikTok data export structure
    3. Has liked and/or favorited videos

    On success, returns the count of liked and favorited videos.
    On failure, returns an appropriate error code and message.

    The upload status is updated based on the validation result:
    - validated: File passed validation
    - invalid: File failed validation

    Args:
        upload_id: The upload ID to validate
        user: Authenticated user from JWT
        settings: Application settings

    Returns:
        ValidateUploadResponse with validation result

    Raises:
        HTTPException: 401 if not authenticated, 403 if not owner,
                      404 if upload not found, 500 if validation fails
    """
    logger.info(
        {
            "event": "validate_upload_requested",
            "upload_id": str(upload_id),
            "user_id": str(user.id),
        }
    )

    # TODO: Implement proper upload lookup from database
    # For now, we'll implement a mock that shows the API contract
    # This will be updated when database integration is complete
    #
    # Expected implementation:
    # 1. Query uploads table for upload_id
    # 2. Verify user_id matches (RLS should handle this)
    # 3. Get storage_path from upload record
    # 4. Download file from Supabase Storage
    # 5. Validate file content
    # 6. Update upload record with validation result

    # Mock: Return 404 for unknown uploads
    # In real implementation, this would be a database lookup
    #
    # upload = await db.query(Upload).filter(Upload.id == upload_id).first()
    # if not upload:
    #     raise HTTPException(status_code=404, detail="Upload not found")
    #
    # if upload.user_id != user.id:
    #     raise HTTPException(status_code=403, detail="Access denied")
    #
    # # Download file from storage
    # storage_service = SupabaseStorageService(settings)
    # file_content = await storage_service.download_file(upload.storage_path)
    #
    # # Validate
    # validation_service = ValidationService()
    # result = await validation_service.validate_upload(
    #     upload_id=upload_id,
    #     user_id=user.id,
    #     file_content=file_content,
    # )
    #
    # # Update upload record
    # if result.should_update_status:
    #     upload.status = result.new_status
    #     error_code = result.result.error_code
    #     upload.validation_error = error_code.value if error_code else None
    #     upload.validation_message = result.result.error_message
    #     upload.validated_at = datetime.now(UTC)
    #     await db.commit()
    #
    # return ValidateUploadResponse(upload_id=upload_id, validation=result.result)

    # Temporary: Return a mock response indicating the endpoint exists
    # but requires database integration
    raise HTTPException(
        status_code=404,
        detail={
            "error": "Upload not found",
            "message": "This endpoint requires database integration. "
            "The upload record lookup is not yet implemented.",
        },
    )


@router.patch(
    "/{upload_id}/scope",
    response_model=ScopeSelectionResponse,
    status_code=200,
    responses={
        200: {"description": "Scope set successfully"},
        400: {"description": "Invalid scope value"},
        401: {"description": "Not authenticated"},
        403: {"description": "Upload belongs to different user"},
        404: {"description": "Upload not found"},
        409: {
            "description": "Upload already processing or scope exceeds tier limit",
            "model": TierLimitExceededError,
        },
        422: {"description": "Upload not validated yet"},
    },
)
async def set_scope(
    upload_id: UUID,
    request: ScopeSelectionRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ScopeSelectionResponse:
    """Set the processing scope for an upload.

    This endpoint allows users to select which videos from their TikTok export
    to process: liked videos only, favorited videos only, or both.

    The selection is validated against the user's subscription tier limits.
    Scope can be changed until processing starts (consent captured).

    Args:
        upload_id: The upload ID to update
        request: The scope selection request
        user: Authenticated user from JWT
        settings: Application settings

    Returns:
        ScopeSelectionResponse with scope details and item counts

    Raises:
        HTTPException:
            - 400: Invalid scope value
            - 401: Not authenticated
            - 403: Upload belongs to different user
            - 404: Upload not found
            - 409: Upload already processing or scope exceeds tier limit
            - 422: Upload not validated yet
    """
    logger.info(
        {
            "event": "scope_selection_requested",
            "upload_id": str(upload_id),
            "user_id": str(user.id),
            "scope": request.scope.value,
        }
    )

    # TODO: Implement proper upload lookup from database
    # For now, we'll implement a mock that shows the API contract
    # This will be updated when database integration is complete
    #
    # Expected implementation:
    # 1. Query uploads table for upload_id
    # 2. Verify user_id matches (RLS should handle this)
    # 3. Check upload status allows scope change
    # 4. Get user's subscription tier from users table
    # 5. Call UploadsService.select_scope()
    # 6. Update upload record with scope and total_items
    # 7. Return response
    #
    # Example:
    # upload = await db.query(Upload).filter(Upload.id == upload_id).first()
    # if not upload:
    #     raise HTTPException(status_code=404, detail="Upload not found")
    #
    # if upload.user_id != user.id:
    #     raise HTTPException(status_code=403, detail="Access denied")
    #
    # user_record = await db.query(User).filter(User.id == user.id).first()
    #
    # service = UploadsService()
    # result = await service.select_scope(
    #     upload_id=upload_id,
    #     user_id=user.id,
    #     scope=request.scope,
    #     user_tier=user_record.subscription_tier,
    #     upload_status=upload.status,
    #     liked_count=upload.validation_liked_count,  # stored during validation
    #     favorited_count=upload.validation_favorited_count,
    # )
    #
    # if not result.success:
    #     if result.error_type == "not_validated":
    #         raise HTTPException(status_code=422, detail=result.error_message)
    #     elif result.error_type == "already_processing":
    #         raise HTTPException(status_code=409, detail=result.error_message)
    #     elif result.error_type == "tier_limit_exceeded":
    #         raise HTTPException(
    #             status_code=409,
    #             detail={
    #                 "error": "TIER_LIMIT_EXCEEDED",
    #                 "message": result.error_message,
    #                 **result.error_details,
    #             },
    #         )
    #
    # # Update upload record
    # upload.scope = request.scope.value
    # upload.total_items = result.response.total_items
    # upload.status = "scope_selected"
    # await db.commit()
    #
    # return result.response

    # Temporary: Return a mock response indicating the endpoint exists
    # but requires database integration
    raise HTTPException(
        status_code=404,
        detail={
            "error": "Upload not found",
            "message": "This endpoint requires database integration. "
            "The upload record lookup is not yet implemented.",
        },
    )


@router.post(
    "/{upload_id}/consent",
    response_model=ConsentResponse,
    status_code=200,
    responses={
        200: {"description": "Consent recorded successfully"},
        400: {"description": "consent_given is false"},
        401: {"description": "Not authenticated"},
        403: {"description": "Upload belongs to different user"},
        404: {"description": "Upload not found"},
        409: {"description": "Consent already recorded"},
        422: {"description": "Scope not selected yet"},
    },
)
async def record_consent(
    upload_id: UUID,
    request: ConsentRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ConsentResponse:
    """Record user consent for data processing.

    This endpoint captures explicit user consent before data processing begins.
    The consent includes version tracking for future consent text changes.

    Processing cannot start without consent being recorded. Once recorded,
    consent cannot be withdrawn through the API (account deletion handles this).

    Args:
        upload_id: The upload ID to record consent for
        request: The consent request with consent_given and version
        user: Authenticated user from JWT
        settings: Application settings

    Returns:
        ConsentResponse with consent details and processing readiness

    Raises:
        HTTPException:
            - 400: consent_given is false (decline should be handled client-side)
            - 401: Not authenticated
            - 403: Upload belongs to different user
            - 404: Upload not found
            - 409: Consent already recorded
            - 422: Scope not selected yet
    """
    logger.info(
        {
            "event": "consent_requested",
            "upload_id": str(upload_id),
            "user_id": str(user.id),
            "consent_given": request.consent_given,
            "consent_version": request.consent_version,
        }
    )

    # Validate that consent_given is true
    if not request.consent_given:
        logger.info(
            {
                "event": "consent_declined",
                "upload_id": str(upload_id),
                "user_id": str(user.id),
            }
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "CONSENT_NOT_GIVEN",
                "message": "Consent must be given to proceed. "
                "If you wish to cancel, use the cancel button.",
            },
        )

    # TODO: Implement proper upload lookup from database
    # For now, we'll implement a mock that shows the API contract
    # This will be updated when database integration is complete
    #
    # Expected implementation:
    # 1. Query uploads table for upload_id
    # 2. Verify user_id matches (RLS should handle this)
    # 3. Check upload status (must be scope_selected)
    # 4. Check consent not already recorded
    # 5. Record consent with version and timestamp
    # 6. Update upload status to "consented"
    # 7. Return response
    #
    # Example:
    # upload = await db.query(Upload).filter(Upload.id == upload_id).first()
    # if not upload:
    #     raise HTTPException(status_code=404, detail="Upload not found")
    #
    # if upload.user_id != user.id:
    #     raise HTTPException(status_code=403, detail="Access denied")
    #
    # # Check scope is selected
    # if upload.status not in ("scope_selected",):
    #     if upload.status in ("pending", "validated"):
    #         raise HTTPException(
    #             status_code=422,
    #             detail={
    #                 "error": "SCOPE_NOT_SELECTED",
    #                 "message": "Please select a processing scope before providing consent.",
    #             },
    #         )
    #     elif upload.consent_given:
    #         raise HTTPException(
    #             status_code=409,
    #             detail={
    #                 "error": "CONSENT_ALREADY_RECORDED",
    #                 "message": "Consent has already been recorded for this upload.",
    #             },
    #         )
    #     else:
    #         raise HTTPException(
    #             status_code=409,
    #             detail={
    #                 "error": "INVALID_STATE",
    #                 "message": f"Upload is in state '{upload.status}' and cannot accept consent.",
    #             },
    #         )
    #
    # # Record consent
    # from datetime import datetime, UTC
    # now = datetime.now(UTC)
    # upload.consent_given = True
    # upload.consent_version = request.consent_version
    # upload.consent_at = now
    # upload.status = "consented"
    # await db.commit()
    #
    # return ConsentResponse(
    #     upload_id=upload_id,
    #     consent_given=True,
    #     consent_version=request.consent_version,
    #     consent_at=now,
    #     ready_to_process=True,
    # )

    # Temporary: Return a mock response indicating the endpoint exists
    # but requires database integration
    raise HTTPException(
        status_code=404,
        detail={
            "error": "Upload not found",
            "message": "This endpoint requires database integration. "
            "The upload record lookup is not yet implemented.",
        },
    )


# ---------------------------------------------------------------------------
# Simplified pipeline trigger (for founder testing)
# ---------------------------------------------------------------------------


class ProcessUploadRequest(BaseModel):
    """Request body for triggering pipeline processing."""

    upload_id: str
    storage_path: str


@router.post(
    "/process",
    status_code=202,
    responses={
        202: {"description": "Pipeline processing triggered"},
        400: {"description": "Missing SQS queue URL configuration"},
        401: {"description": "Not authenticated"},
        500: {"description": "Failed to send SQS message"},
    },
)
async def process_upload(
    request: ProcessUploadRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Trigger pipeline processing for an uploaded TikTok export.

    Simplified endpoint for founder testing — sends an SQS message to kick off
    the 4-step pipeline (parse → enrich → subtitles → embed) without requiring
    the full validate → scope → consent wizard.

    Args:
        request: Upload ID and storage path from presigned URL response.
        user: Authenticated user from JWT.
        settings: Application settings.

    Returns:
        202 with message_id on success.
    """
    if not settings.sqs_queue_url:
        raise HTTPException(
            status_code=400,
            detail="Pipeline processing is not configured (missing SQS queue URL).",
        )

    sqs_body = {
        "upload_id": request.upload_id,
        "user_id": str(user.id),
        "storage_path": request.storage_path,
        "scope": "both",
    }

    try:
        sqs_kwargs: dict = {
            "region_name": settings.aws_region,
            "aws_access_key_id": settings.aws_access_key_id,
            "aws_secret_access_key": settings.aws_secret_access_key,
        }
        if settings.aws_endpoint_url:
            sqs_kwargs["endpoint_url"] = settings.aws_endpoint_url

        sqs_client = boto3.client("sqs", **sqs_kwargs)
        response = sqs_client.send_message(
            QueueUrl=settings.sqs_queue_url,
            MessageBody=json.dumps(sqs_body),
        )

        logger.info(
            {
                "event": "pipeline_triggered",
                "upload_id": request.upload_id,
                "user_id": str(user.id),
                "message_id": response.get("MessageId"),
            }
        )

        return {
            "status": "processing",
            "message_id": response.get("MessageId"),
            "upload_id": request.upload_id,
        }

    except Exception as e:
        logger.error(
            {
                "event": "sqs_send_failed",
                "upload_id": request.upload_id,
                "user_id": str(user.id),
                "error": str(e),
            }
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to trigger pipeline processing. Please try again.",
        )
