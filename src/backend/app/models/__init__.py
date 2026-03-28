"""Models package.

Contains both Pydantic schemas (API contracts) and SQLAlchemy ORM models.
"""

from pydantic import BaseModel

from app.models.auth import (
    AccountDeletionError,
    AccountDeletionResponse,
    AuthenticatedUser,
    AuthErrorCode,
    AuthErrorResponse,
    DeletionErrorCode,
)
from app.models.collection import Collection, CollectionItem
from app.models.conversation import Conversation, Message
from app.models.cost_model import CostModel
from app.models.media_event import MediaEvent
from app.models.processing_step import ProcessingStep
from app.models.prompt_template import PromptTemplate
from app.models.upload import Upload
from app.models.upload_pipeline_run import UploadPipelineRun
from app.models.user import User


# Pydantic schemas for API
class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    version: str


__all__ = [
    # Pydantic - Auth
    "AccountDeletionError",
    "AccountDeletionResponse",
    "AuthenticatedUser",
    "AuthErrorCode",
    "AuthErrorResponse",
    "DeletionErrorCode",
    # Pydantic - API
    "HealthResponse",
    # SQLAlchemy
    "Collection",
    "CollectionItem",
    "Conversation",
    "CostModel",
    "Message",
    "MediaEvent",
    "ProcessingStep",
    "PromptTemplate",
    "Upload",
    "UploadPipelineRun",
    "User",
]
