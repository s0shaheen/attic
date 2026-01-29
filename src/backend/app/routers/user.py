"""User management routes.

This module contains endpoints for user account management,
including account deletion for GDPR compliance.
"""

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user
from app.core.config import Settings, get_settings
from app.models.auth import (
    AccountDeletionResponse,
    AuthenticatedUser,
    DeletionErrorCode,
)
from app.services.user_deletion import UserDeletionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user", tags=["user"])


@router.delete(
    "/me",
    response_model=AccountDeletionResponse,
    status_code=202,
    responses={
        202: {"description": "Account deletion initiated successfully"},
        401: {"description": "Not authenticated"},
        500: {"description": "Deletion failed"},
    },
)
async def delete_current_user(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AccountDeletionResponse:
    """Delete the current user's account and all associated data.

    This endpoint initiates GDPR-compliant account deletion:
    - Deletes user files from Supabase Storage
    - Deletes user from Supabase Auth
    - Sends confirmation email (if email available)

    The user should be signed out client-side after calling this endpoint.

    Returns:
        AccountDeletionResponse with deletion confirmation

    Raises:
        HTTPException: 401 if not authenticated, 500 if deletion fails
    """
    deletion_service = UserDeletionService(settings)

    result = await deletion_service.delete_user_account(
        user_id=user.id,
        email=user.email,
    )

    if not result.success:
        logger.error(
            {
                "event": "delete_user_endpoint_failed",
                "user_id": str(user.id),
                "error": result.error,
            }
        )
        raise HTTPException(
            status_code=500,
            detail={
                "detail": result.error or "Account deletion failed",
                "code": DeletionErrorCode.DELETION_FAILED,
            },
        )

    return AccountDeletionResponse(
        message="Account deletion initiated",
        deletion_scheduled_at=datetime.now(UTC),
        confirmation_email_sent=result.email_sent,
    )
