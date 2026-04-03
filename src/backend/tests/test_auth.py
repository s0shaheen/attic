"""Tests for the JWT authentication middleware."""

import time
from uuid import uuid4

import jwt
import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.auth import get_current_user, get_current_user_optional
from app.models.auth import AuthenticatedUser, AuthErrorCode

# Test configuration - must match the env var above
TEST_JWT_SECRET = "test-jwt-secret-for-testing-only"
TEST_SUPABASE_URL = "https://test-project.supabase.co"
TEST_USER_ID = str(uuid4())
TEST_USER_EMAIL = "test@example.com"


def create_test_token(
    user_id: str = TEST_USER_ID,
    email: str | None = TEST_USER_EMAIL,
    expires_in: int = 3600,
    issuer: str | None = None,
    audience: str | None = None,
    secret: str = TEST_JWT_SECRET,
    algorithm: str = "HS256",
    include_iat: bool = True,
    include_exp: bool = True,
    include_sub: bool = True,
) -> str:
    """Create a test JWT token with configurable claims.

    Args:
        user_id: The user ID for the 'sub' claim
        email: Optional email to include in token
        expires_in: Seconds until token expires (use negative for expired)
        issuer: Token issuer (defaults to TEST_SUPABASE_URL/auth/v1)
        audience: Token audience (defaults to 'authenticated')
        secret: Secret key for signing
        algorithm: Algorithm for signing
        include_iat: Whether to include 'iat' claim
        include_exp: Whether to include 'exp' claim
        include_sub: Whether to include 'sub' claim

    Returns:
        Encoded JWT token string
    """
    now = int(time.time())

    payload: dict = {}

    if include_sub:
        payload["sub"] = user_id

    if include_iat:
        payload["iat"] = now

    if include_exp:
        payload["exp"] = now + expires_in

    if issuer is not None:
        payload["iss"] = issuer
    else:
        payload["iss"] = f"{TEST_SUPABASE_URL}/auth/v1"

    if audience is not None:
        payload["aud"] = audience
    else:
        payload["aud"] = "authenticated"

    if email:
        payload["email"] = email

    return jwt.encode(payload, secret, algorithm=algorithm)


def create_test_app() -> FastAPI:
    """Create a test FastAPI app with auth endpoints."""
    app = FastAPI()

    @app.get("/protected")
    async def protected_route(user: AuthenticatedUser = Depends(get_current_user)):
        return {"user_id": str(user.id), "email": user.email}

    @app.get("/optional")
    async def optional_route(
        user: AuthenticatedUser | None = Depends(get_current_user_optional),
    ):
        if user:
            return {"user_id": str(user.id), "email": user.email}
        return {"user_id": None, "email": None}

    return app


@pytest.fixture
async def test_client():
    """Create test client with settings from environment."""
    app = create_test_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# =============================================================================
# Tests for get_current_user (required auth)
# =============================================================================


@pytest.mark.asyncio
async def test_get_current_user_valid_token_returns_user(test_client: AsyncClient):
    """Valid JWT returns AuthenticatedUser with correct user_id."""
    token = create_test_token()
    response = await test_client.get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == TEST_USER_ID
    assert data["email"] == TEST_USER_EMAIL


@pytest.mark.asyncio
async def test_get_current_user_valid_token_without_email(test_client: AsyncClient):
    """Valid JWT without email returns user with None email."""
    token = create_test_token(email=None)
    response = await test_client.get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == TEST_USER_ID
    assert data["email"] is None


@pytest.mark.asyncio
async def test_get_current_user_missing_header_returns_401(test_client: AsyncClient):
    """Missing Authorization header returns 401 with MISSING_AUTH code."""
    response = await test_client.get("/protected")

    assert response.status_code == 401
    data = response.json()
    assert data["detail"]["code"] == AuthErrorCode.MISSING_AUTH
    assert "authorization" in data["detail"]["detail"].lower()


@pytest.mark.asyncio
async def test_get_current_user_invalid_format_returns_401(test_client: AsyncClient):
    """Invalid token format returns 401 with INVALID_TOKEN_FORMAT code."""
    response = await test_client.get(
        "/protected",
        headers={"Authorization": "Bearer not-a-valid-jwt"},
    )

    assert response.status_code == 401
    data = response.json()
    assert data["detail"]["code"] == AuthErrorCode.INVALID_TOKEN_FORMAT


@pytest.mark.asyncio
async def test_get_current_user_expired_token_returns_401(test_client: AsyncClient):
    """Expired token returns 401 with TOKEN_EXPIRED code."""
    token = create_test_token(expires_in=-3600)  # Expired 1 hour ago
    response = await test_client.get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    data = response.json()
    assert data["detail"]["code"] == AuthErrorCode.TOKEN_EXPIRED


@pytest.mark.asyncio
async def test_get_current_user_invalid_signature_returns_401(test_client: AsyncClient):
    """Token signed with wrong secret returns 401 with INVALID_SIGNATURE code."""
    token = create_test_token(secret="wrong-secret")
    response = await test_client.get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    data = response.json()
    assert data["detail"]["code"] == AuthErrorCode.INVALID_SIGNATURE


@pytest.mark.asyncio
async def test_get_current_user_invalid_issuer_returns_401(test_client: AsyncClient):
    """Token with wrong issuer returns 401 with INVALID_CLAIMS code."""
    token = create_test_token(issuer="https://wrong-issuer.com/auth/v1")
    response = await test_client.get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    data = response.json()
    assert data["detail"]["code"] == AuthErrorCode.INVALID_CLAIMS


@pytest.mark.asyncio
async def test_get_current_user_invalid_audience_returns_401(test_client: AsyncClient):
    """Token with wrong audience returns 401 with INVALID_CLAIMS code."""
    token = create_test_token(audience="wrong-audience")
    response = await test_client.get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    data = response.json()
    assert data["detail"]["code"] == AuthErrorCode.INVALID_CLAIMS


@pytest.mark.asyncio
async def test_get_current_user_missing_sub_claim_returns_401(test_client: AsyncClient):
    """Token without 'sub' claim returns 401 with INVALID_CLAIMS code."""
    token = create_test_token(include_sub=False)
    response = await test_client.get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    data = response.json()
    assert data["detail"]["code"] == AuthErrorCode.INVALID_CLAIMS


@pytest.mark.asyncio
async def test_get_current_user_missing_exp_claim_returns_401(test_client: AsyncClient):
    """Token without 'exp' claim returns 401 with INVALID_CLAIMS code."""
    token = create_test_token(include_exp=False)
    response = await test_client.get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    data = response.json()
    assert data["detail"]["code"] == AuthErrorCode.INVALID_CLAIMS


@pytest.mark.asyncio
async def test_get_current_user_missing_iat_claim_returns_401(test_client: AsyncClient):
    """Token without 'iat' claim returns 401 with INVALID_CLAIMS code."""
    token = create_test_token(include_iat=False)
    response = await test_client.get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    data = response.json()
    assert data["detail"]["code"] == AuthErrorCode.INVALID_CLAIMS


@pytest.mark.asyncio
async def test_get_current_user_invalid_sub_uuid_returns_401(test_client: AsyncClient):
    """Token with non-UUID 'sub' claim returns 401 with INVALID_CLAIMS code."""
    token = create_test_token(user_id="not-a-valid-uuid")
    response = await test_client.get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    data = response.json()
    assert data["detail"]["code"] == AuthErrorCode.INVALID_CLAIMS


# =============================================================================
# Tests for get_current_user_optional (optional auth)
# =============================================================================


@pytest.mark.asyncio
async def test_get_current_user_optional_no_token_returns_none(test_client: AsyncClient):
    """No token with optional auth returns null user."""
    response = await test_client.get("/optional")

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] is None
    assert data["email"] is None


@pytest.mark.asyncio
async def test_get_current_user_optional_valid_token_returns_user(test_client: AsyncClient):
    """Valid token with optional auth returns user."""
    token = create_test_token()
    response = await test_client.get(
        "/optional",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == TEST_USER_ID
    assert data["email"] == TEST_USER_EMAIL


@pytest.mark.asyncio
async def test_get_current_user_optional_invalid_token_returns_401(test_client: AsyncClient):
    """Invalid token with optional auth returns 401 (not None)."""
    token = create_test_token(secret="wrong-secret")
    response = await test_client.get(
        "/optional",
        headers={"Authorization": f"Bearer {token}"},
    )

    # If a token is provided, it must be valid
    assert response.status_code == 401
    data = response.json()
    assert data["detail"]["code"] == AuthErrorCode.INVALID_SIGNATURE


@pytest.mark.asyncio
async def test_get_current_user_optional_expired_token_returns_401(test_client: AsyncClient):
    """Expired token with optional auth returns 401 (not None)."""
    token = create_test_token(expires_in=-3600)
    response = await test_client.get(
        "/optional",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    data = response.json()
    assert data["detail"]["code"] == AuthErrorCode.TOKEN_EXPIRED


# =============================================================================
# Integration tests
# =============================================================================


@pytest.mark.asyncio
async def test_protected_endpoint_user_id_from_token(test_client: AsyncClient):
    """User ID in response matches the sub claim from token."""
    user_id = str(uuid4())
    token = create_test_token(user_id=user_id)
    response = await test_client.get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == user_id


@pytest.mark.asyncio
async def test_auth_error_includes_www_authenticate_header(test_client: AsyncClient):
    """401 responses include WWW-Authenticate header."""
    response = await test_client.get("/protected")

    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers
    assert response.headers["WWW-Authenticate"] == "Bearer"
