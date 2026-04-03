"""Upload management routes.

Endpoint flow:
  /presigned-url ──► /validate ──► /scope ──► /consent ──► /process
       │                                                       │
       └── creates Upload record                    ├── SQS (prod)
                                                    └── inline (dev)
"""

import json
import logging
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

import boto3
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.auth import get_current_user
from app.core.rate_limit import check_upload_rate_limit
from app.db.session import get_db
from app.models.auth import AuthenticatedUser
from app.models.upload import Upload
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
    ValidationResult,
)
from app.services.uploads import UploadService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


# ---------------------------------------------------------------------------
# Helper: look up upload and verify ownership
# ---------------------------------------------------------------------------


async def _get_upload_or_404(upload_id: UUID, user_id: UUID, db: AsyncSession) -> Upload:
    """Query upload by ID and verify ownership."""
    result = await db.execute(select(Upload).where(Upload.id == upload_id))
    upload = result.scalar_one_or_none()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    if upload.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return upload


# ---------------------------------------------------------------------------
# POST /presigned-url
# ---------------------------------------------------------------------------


@router.post(
    "/presigned-url",
    response_model=PresignedUrlResponse,
    status_code=200,
    responses={
        200: {"description": "Presigned URL generated successfully"},
        400: {"description": "Invalid content type", "model": UploadErrorResponse},
        401: {"description": "Not authenticated"},
        403: {"description": "Upload limit exceeded", "model": UploadErrorResponse},
        500: {"description": "Failed to generate presigned URL", "model": UploadErrorResponse},
    },
)
async def create_presigned_url(
    request: PresignedUrlRequest,
    user: Annotated[AuthenticatedUser, Depends(check_upload_rate_limit)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PresignedUrlResponse:
    """Generate a presigned URL and create a pending upload record."""
    upload_service = UploadService(settings)

    # Tier/count defaults — full tier enforcement is a follow-up
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

    # Create upload record in DB (fixes FK violation when pipeline runs)
    upload = Upload(
        id=result.upload_id,
        user_id=user.id,
        source_platform="tiktok",
        status="pending",
    )
    db.add(upload)
    # get_db() auto-commits on success

    return PresignedUrlResponse(
        upload_id=result.upload_id,  # type: ignore[arg-type]
        presigned_url=result.presigned_url,  # type: ignore[arg-type]
        storage_path=result.storage_path,  # type: ignore[arg-type]
        expires_at=result.expires_at,  # type: ignore[arg-type]
        max_file_size=result.max_file_size,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# POST /{upload_id}/validate
# ---------------------------------------------------------------------------
# Note: validate, scope, and consent endpoints use get_current_user (not
# check_upload_rate_limit) because they operate on existing uploads owned by
# the user. Abuse is gated by presigned-url rate limiting — you can't call
# these without first creating an upload through the rate-limited endpoint.


@router.post(
    "/{upload_id}/validate",
    response_model=ValidateUploadResponse,
    status_code=200,
    responses={
        200: {"description": "Validation complete (check valid field for result)"},
        401: {"description": "Not authenticated"},
        403: {"description": "Upload belongs to different user"},
        404: {"description": "Upload not found"},
    },
)
async def validate_upload(
    upload_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ValidateUploadResponse:
    """Validate an uploaded TikTok export file.

    Marks upload as validated. Full ZIP download + content validation
    is a follow-up — for now this advances the state machine so the
    upload flow can proceed.
    """
    upload = await _get_upload_or_404(upload_id, user.id, db)

    now = datetime.now(UTC)
    upload.status = "validated"
    upload.validated_at = now

    logger.info(
        {
            "event": "upload_validated",
            "upload_id": str(upload_id),
            "user_id": str(user.id),
        }
    )

    return ValidateUploadResponse(
        upload_id=upload_id,
        validation=ValidationResult(
            valid=True,
            liked_count=0,
            favorited_count=0,
        ),
    )


# ---------------------------------------------------------------------------
# PATCH /{upload_id}/scope
# ---------------------------------------------------------------------------


@router.patch(
    "/{upload_id}/scope",
    response_model=ScopeSelectionResponse,
    status_code=200,
    responses={
        200: {"description": "Scope set successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Upload belongs to different user"},
        404: {"description": "Upload not found"},
        409: {"description": "Upload already processing", "model": TierLimitExceededError},
        422: {"description": "Upload not validated yet"},
    },
)
async def set_scope(
    upload_id: UUID,
    request: ScopeSelectionRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ScopeSelectionResponse:
    """Set the processing scope for an upload."""
    upload = await _get_upload_or_404(upload_id, user.id, db)

    # Check status allows scope change
    if upload.status not in ("validated", "scope_selected"):
        if upload.status == "pending":
            raise HTTPException(status_code=422, detail="Upload not validated yet")
        raise HTTPException(
            status_code=409,
            detail=f"Upload is in state '{upload.status}' and cannot change scope",
        )

    upload.scope = request.scope.value
    upload.status = "scope_selected"

    logger.info(
        {
            "event": "scope_selected",
            "upload_id": str(upload_id),
            "user_id": str(user.id),
            "scope": request.scope.value,
        }
    )

    return ScopeSelectionResponse(
        upload_id=upload_id,
        scope=request.scope,
        total_items=0,
        liked_count=0,
        favorited_count=0,
        tier_limit=500,
        within_limit=True,
        estimated_processing_minutes=5,
        ready_for_consent=True,
    )


# ---------------------------------------------------------------------------
# POST /{upload_id}/consent
# ---------------------------------------------------------------------------


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
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConsentResponse:
    """Record user consent for data processing."""
    if not request.consent_given:
        raise HTTPException(
            status_code=400,
            detail={"error": "CONSENT_NOT_GIVEN", "message": "Consent must be given to proceed."},
        )

    upload = await _get_upload_or_404(upload_id, user.id, db)

    # Check status
    if upload.status not in ("scope_selected",):
        if upload.status in ("pending", "validated"):
            raise HTTPException(status_code=422, detail="Select a processing scope first")
        elif upload.consent_given:
            raise HTTPException(status_code=409, detail="Consent already recorded")
        else:
            raise HTTPException(
                status_code=409,
                detail=f"Upload is in state '{upload.status}' and cannot accept consent",
            )

    now = datetime.now(UTC)
    upload.consent_given = True
    upload.consent_version = request.consent_version
    upload.consent_at = now
    upload.status = "consented"

    logger.info(
        {
            "event": "consent_recorded",
            "upload_id": str(upload_id),
            "user_id": str(user.id),
        }
    )

    return ConsentResponse(
        upload_id=upload_id,
        consent_given=True,
        consent_version=request.consent_version,
        consent_at=now,
        ready_to_process=True,
    )


# ---------------------------------------------------------------------------
# POST /process — trigger pipeline (SQS or inline)
# ---------------------------------------------------------------------------


class ProcessUploadRequest(BaseModel):
    """Request body for triggering pipeline processing."""

    upload_id: UUID
    storage_path: str
    source_platform: Literal["tiktok", "instagram"] = "tiktok"


@router.post(
    "/process",
    status_code=202,
    responses={
        202: {"description": "Pipeline processing triggered"},
        401: {"description": "Not authenticated"},
        500: {"description": "Failed to send SQS message"},
    },
)
async def process_upload(
    request: ProcessUploadRequest,
    user: Annotated[AuthenticatedUser, Depends(check_upload_rate_limit)],
    settings: Annotated[Settings, Depends(get_settings)],
    background_tasks: BackgroundTasks,
) -> dict:
    """Trigger pipeline processing for an uploaded TikTok export.

    - If SQS_QUEUE_URL is configured: sends SQS message (production path)
    - If not: runs pipeline inline via BackgroundTasks (dev path)
    """
    if not settings.sqs_queue_url:
        # Dev mode: run pipeline inline via background thread
        def _run_inline() -> None:
            try:
                from app.services.pipeline import run_pipeline

                run_pipeline(
                    upload_id=str(request.upload_id),
                    user_id=str(user.id),
                    storage_path=request.storage_path,
                    scope="both",
                    source_platform=request.source_platform,
                )
            except Exception:
                logger.exception(
                    "Inline pipeline failed",
                    extra={"upload_id": str(request.upload_id)},
                )

        background_tasks.add_task(_run_inline)

        logger.info(
            {
                "event": "pipeline_inline_triggered",
                "upload_id": str(request.upload_id),
                "user_id": str(user.id),
            }
        )

        return {
            "status": "processing",
            "message_id": "inline",
            "upload_id": str(request.upload_id),
        }

    # Production path: send to SQS
    sqs_body = {
        "upload_id": str(request.upload_id),
        "user_id": str(user.id),
        "storage_path": request.storage_path,
        "scope": "both",
        "source_platform": request.source_platform,
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
                "upload_id": str(request.upload_id),
                "user_id": str(user.id),
                "message_id": response.get("MessageId"),
            }
        )

        return {
            "status": "processing",
            "message_id": response.get("MessageId"),
            "upload_id": str(request.upload_id),
        }

    except Exception as e:
        logger.error(
            {
                "event": "sqs_send_failed",
                "upload_id": str(request.upload_id),
                "user_id": str(user.id),
                "error": str(e),
            }
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to trigger pipeline processing. Please try again.",
        )
