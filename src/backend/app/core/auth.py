"""JWT authentication and authorization for FastAPI.

This module provides FastAPI dependencies for validating Supabase JWTs
and extracting user information from tokens. All protected endpoints
should use get_current_user to require authentication.

Usage:
    @router.get("/protected")
    async def protected_route(user: AuthenticatedUser = Depends(get_current_user)):
        return {"user_id": str(user.id)}

    @router.get("/optional-auth")
    async def optional_auth_route(
        user: AuthenticatedUser | None = Depends(get_current_user_optional)
    ):
        if user:
            return {"user_id": str(user.id)}
        return {"user_id": None}
"""

import logging
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.models.auth import AuthenticatedUser, AuthErrorCode, AuthErrorResponse

logger = logging.getLogger(__name__)

# HTTP Bearer scheme for extracting tokens from Authorization header
# auto_error=False allows us to provide custom error messages
security = HTTPBearer(auto_error=False)


def _create_auth_error(detail: str, code: str) -> HTTPException:
    """Create a 401 HTTPException with AuthErrorResponse body.

    Args:
        detail: Human-readable error message
        code: Machine-readable error code

    Returns:
        HTTPException with 401 status and structured error body
    """
    return HTTPException(
        status_code=401,
        detail=AuthErrorResponse(detail=detail, code=code).model_dump(),
        headers={"WWW-Authenticate": "Bearer"},
    )


def _validate_and_decode_token(
    token: str,
    settings: Settings,
) -> dict:
    """Validate JWT signature and decode claims.

    Args:
        token: The JWT access token to validate
        settings: Application settings containing JWT secret

    Returns:
        Decoded JWT payload dict

    Raises:
        HTTPException: 401 error if token is invalid
    """
    try:
        # Decode and verify the JWT
        # - verify=True (default) checks signature
        # - algorithms specifies allowed algorithms (HS256 for Supabase)
        # - issuer validates the 'iss' claim
        # - audience validates the 'aud' claim
        # - options require_exp=True ensures expiry is checked
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            issuer=f"{settings.supabase_url}/auth/v1",
            audience="authenticated",
            options={
                "require": ["exp", "iat", "sub"],
            },
        )
        return payload

    except jwt.ExpiredSignatureError:
        logger.info({"event": "auth_failed", "reason": AuthErrorCode.TOKEN_EXPIRED})
        raise _create_auth_error("Token has expired", AuthErrorCode.TOKEN_EXPIRED)

    except jwt.InvalidSignatureError:
        logger.info({"event": "auth_failed", "reason": AuthErrorCode.INVALID_SIGNATURE})
        raise _create_auth_error("Invalid token signature", AuthErrorCode.INVALID_SIGNATURE)

    except jwt.InvalidIssuerError:
        logger.info({"event": "auth_failed", "reason": AuthErrorCode.INVALID_CLAIMS})
        raise _create_auth_error("Invalid token issuer", AuthErrorCode.INVALID_CLAIMS)

    except jwt.InvalidAudienceError:
        logger.info({"event": "auth_failed", "reason": AuthErrorCode.INVALID_CLAIMS})
        raise _create_auth_error("Invalid token audience", AuthErrorCode.INVALID_CLAIMS)

    except jwt.MissingRequiredClaimError as e:
        logger.info(
            {
                "event": "auth_failed",
                "reason": AuthErrorCode.INVALID_CLAIMS,
                "claim": str(e),
            }
        )
        raise _create_auth_error(f"Missing required claim: {e}", AuthErrorCode.INVALID_CLAIMS)

    except jwt.DecodeError:
        logger.info({"event": "auth_failed", "reason": AuthErrorCode.INVALID_TOKEN_FORMAT})
        raise _create_auth_error("Invalid token format", AuthErrorCode.INVALID_TOKEN_FORMAT)

    except jwt.PyJWTError as e:
        logger.info(
            {
                "event": "auth_failed",
                "reason": AuthErrorCode.INVALID_TOKEN_FORMAT,
                "error": str(e),
            }
        )
        raise _create_auth_error("Invalid token", AuthErrorCode.INVALID_TOKEN_FORMAT)


def _extract_user_from_payload(payload: dict) -> AuthenticatedUser:
    """Extract AuthenticatedUser from validated JWT payload.

    Args:
        payload: Decoded and validated JWT payload

    Returns:
        AuthenticatedUser with id and optional email

    Raises:
        HTTPException: 401 error if sub claim is invalid
    """
    sub = payload.get("sub")
    if not sub:
        raise _create_auth_error("Missing user ID in token", AuthErrorCode.INVALID_CLAIMS)

    try:
        user_id = UUID(sub)
    except ValueError:
        raise _create_auth_error("Invalid user ID format in token", AuthErrorCode.INVALID_CLAIMS)

    # Email is optional in Supabase tokens
    email = payload.get("email")

    return AuthenticatedUser(id=user_id, email=email)


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticatedUser:
    """FastAPI dependency that validates JWT and returns the authenticated user.

    This dependency should be used on all protected endpoints. It extracts
    the Bearer token from the Authorization header, validates it against
    the Supabase JWT secret, and returns the authenticated user.

    Args:
        request: The incoming HTTP request (for logging)
        credentials: The extracted Bearer token credentials
        settings: Application settings with JWT secret

    Returns:
        AuthenticatedUser with validated user ID and optional email

    Raises:
        HTTPException: 401 Unauthorized if token is missing, invalid, or expired

    Example:
        @router.get("/me")
        async def get_me(user: AuthenticatedUser = Depends(get_current_user)):
            return {"user_id": str(user.id)}
    """
    if credentials is None:
        logger.info(
            {
                "event": "auth_failed",
                "reason": AuthErrorCode.MISSING_AUTH,
                "path": request.url.path,
            }
        )
        raise _create_auth_error("Missing authorization header", AuthErrorCode.MISSING_AUTH)

    # Validate and decode the token
    payload = _validate_and_decode_token(credentials.credentials, settings)

    # Extract user from validated payload
    user = _extract_user_from_payload(payload)

    return user


async def get_current_user_optional(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticatedUser | None:
    """FastAPI dependency that optionally validates JWT.

    Use this for endpoints that can work with or without authentication,
    such as public pages that show additional features for logged-in users.

    If no Authorization header is provided, returns None.
    If a token is provided, it must be valid or a 401 error is raised.

    Args:
        request: The incoming HTTP request
        credentials: The extracted Bearer token credentials (may be None)
        settings: Application settings with JWT secret

    Returns:
        AuthenticatedUser if valid token provided, None if no token

    Raises:
        HTTPException: 401 Unauthorized if token is provided but invalid

    Example:
        @router.get("/content")
        async def get_content(
            user: AuthenticatedUser | None = Depends(get_current_user_optional)
        ):
            if user:
                return {"content": "premium", "user_id": str(user.id)}
            return {"content": "basic"}
    """
    if credentials is None:
        return None

    # If credentials provided, they must be valid
    payload = _validate_and_decode_token(credentials.credentials, settings)
    return _extract_user_from_payload(payload)
