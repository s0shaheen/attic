"""Auth-related Pydantic models for API contracts."""

from uuid import UUID

from pydantic import BaseModel, Field


class AuthenticatedUser(BaseModel):
    """User info extracted from validated JWT.

    This model is returned by auth dependencies and provides
    the authenticated user's ID to route handlers.

    Attributes:
        id: The user's UUID (from JWT 'sub' claim)
        email: The user's email (from JWT 'email' claim, may be None)
    """

    id: UUID = Field(description="User ID extracted from JWT 'sub' claim")
    email: str | None = Field(default=None, description="User email from JWT, may not be present")


class AuthErrorResponse(BaseModel):
    """Error response for authentication failures.

    This model provides structured error information for 401 responses,
    including a machine-readable code for debugging.

    Attributes:
        detail: Human-readable error message
        code: Machine-readable error code for debugging
    """

    detail: str = Field(description="Human-readable error message")
    code: str = Field(description="Machine-readable error code")


# Error codes for auth failures
class AuthErrorCode:
    """Constants for auth error codes."""

    MISSING_AUTH = "MISSING_AUTH"
    INVALID_TOKEN_FORMAT = "INVALID_TOKEN_FORMAT"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    INVALID_CLAIMS = "INVALID_CLAIMS"
