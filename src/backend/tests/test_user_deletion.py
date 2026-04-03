"""Tests for user deletion functionality."""

import os
import time
from unittest.mock import AsyncMock, patch
from uuid import uuid4

# Set environment variables BEFORE importing anything from app
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("SUPABASE_URL", "https://test-project.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-for-testing-only")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test-aws-key")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test-aws-secret")
os.environ.setdefault("APIFY_API_TOKEN", "test-apify-token")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("STRIPE_SECRET_KEY", "test-stripe-key")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "test-stripe-webhook")
os.environ.setdefault("RESEND_API_KEY", "test-resend-key")

import jwt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response

from app.config import Settings
from app.models.auth import AuthErrorCode, DeletionErrorCode
from app.routers.user import router as user_router
from app.services.user_deletion import DeletionResult, UserDeletionService

# Test configuration
TEST_JWT_SECRET = "test-jwt-secret-for-testing-only"
TEST_SUPABASE_URL = "https://test-project.supabase.co"
TEST_USER_ID = str(uuid4())
TEST_USER_EMAIL = "test@example.com"


def create_test_token(
    user_id: str = TEST_USER_ID,
    email: str | None = TEST_USER_EMAIL,
    expires_in: int = 3600,
) -> str:
    """Create a test JWT token."""
    now = int(time.time())
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + expires_in,
        "iss": f"{TEST_SUPABASE_URL}/auth/v1",
        "aud": "authenticated",
    }
    if email:
        payload["email"] = email
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


def create_test_app() -> FastAPI:
    """Create a test FastAPI app with user routes."""
    app = FastAPI()
    app.include_router(user_router)
    return app


@pytest.fixture
async def test_client():
    """Create test client with user routes."""
    app = create_test_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = Settings(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        supabase_url=TEST_SUPABASE_URL,
        supabase_service_key="test-service-key",
        supabase_jwt_secret=TEST_JWT_SECRET,
        aws_access_key_id="test-aws-key",
        aws_secret_access_key="test-aws-secret",
        apify_api_token="test-apify-token",
        openai_api_key="test-openai-key",
        stripe_secret_key="test-stripe-key",
        stripe_webhook_secret="test-stripe-webhook",
        resend_api_key="test-resend-key",
    )
    return settings


# =============================================================================
# Tests for UserDeletionService
# =============================================================================


@pytest.mark.asyncio
async def test_delete_user_storage_files_no_files_returns_true(mock_settings):
    """When user has no storage files, deletion returns True."""
    service = UserDeletionService(mock_settings)
    user_id = uuid4()

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = Response(status_code=404)

        result = await service.delete_user_storage_files(user_id)

        assert result is True


@pytest.mark.asyncio
async def test_delete_user_storage_files_with_files_returns_true(mock_settings):
    """When user has storage files, they are deleted successfully."""
    service = UserDeletionService(mock_settings)
    user_id = uuid4()

    async def mock_request(*args, **kwargs):
        url = args[0] if args else kwargs.get("url", "")
        if "list" in str(url):
            return Response(
                status_code=200,
                json=[{"name": "file1.zip"}, {"name": "file2.zip"}],
            )
        else:
            return Response(status_code=200)

    with patch("httpx.AsyncClient.post", side_effect=mock_request):
        with patch("httpx.AsyncClient.delete", return_value=Response(status_code=200)):
            result = await service.delete_user_storage_files(user_id)

            assert result is True


@pytest.mark.asyncio
async def test_delete_user_storage_files_timeout_returns_true(mock_settings):
    """Storage timeout returns True (non-blocking)."""
    import httpx

    service = UserDeletionService(mock_settings)
    user_id = uuid4()

    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("timeout")):
        result = await service.delete_user_storage_files(user_id)

        # Storage failure shouldn't block deletion
        assert result is True


@pytest.mark.asyncio
async def test_delete_user_from_auth_success_returns_true(mock_settings):
    """Successful auth deletion returns True."""
    service = UserDeletionService(mock_settings)
    user_id = uuid4()

    with patch("httpx.AsyncClient.delete", return_value=Response(status_code=200)):
        result = await service.delete_user_from_auth(user_id)

        assert result is True


@pytest.mark.asyncio
async def test_delete_user_from_auth_already_deleted_returns_true(mock_settings):
    """User already deleted returns True."""
    service = UserDeletionService(mock_settings)
    user_id = uuid4()

    with patch("httpx.AsyncClient.delete", return_value=Response(status_code=404)):
        result = await service.delete_user_from_auth(user_id)

        assert result is True


@pytest.mark.asyncio
async def test_delete_user_from_auth_failure_returns_false(mock_settings):
    """Auth deletion failure returns False."""
    service = UserDeletionService(mock_settings)
    user_id = uuid4()

    with patch(
        "httpx.AsyncClient.delete",
        return_value=Response(status_code=500, text="Internal error"),
    ):
        result = await service.delete_user_from_auth(user_id)

        assert result is False


@pytest.mark.asyncio
async def test_delete_user_from_auth_timeout_returns_false(mock_settings):
    """Auth timeout returns False (required operation)."""
    import httpx

    service = UserDeletionService(mock_settings)
    user_id = uuid4()

    with patch("httpx.AsyncClient.delete", side_effect=httpx.TimeoutException("timeout")):
        result = await service.delete_user_from_auth(user_id)

        assert result is False


@pytest.mark.asyncio
async def test_send_deletion_confirmation_email_no_email_returns_false(mock_settings):
    """No email returns False (skipped)."""
    service = UserDeletionService(mock_settings)
    user_id = uuid4()

    result = await service.send_deletion_confirmation_email(None, user_id)

    assert result is False


@pytest.mark.asyncio
async def test_send_deletion_confirmation_email_success_returns_true(mock_settings):
    """Successful email send returns True."""
    service = UserDeletionService(mock_settings)
    user_id = uuid4()

    with patch("httpx.AsyncClient.post", return_value=Response(status_code=200)):
        result = await service.send_deletion_confirmation_email("test@example.com", user_id)

        assert result is True


@pytest.mark.asyncio
async def test_send_deletion_confirmation_email_failure_returns_false(mock_settings):
    """Email failure returns False (non-blocking)."""
    service = UserDeletionService(mock_settings)
    user_id = uuid4()

    with patch("httpx.AsyncClient.post", return_value=Response(status_code=500)):
        result = await service.send_deletion_confirmation_email("test@example.com", user_id)

        assert result is False


@pytest.mark.asyncio
async def test_delete_user_account_success(mock_settings):
    """Full account deletion succeeds."""
    service = UserDeletionService(mock_settings)
    user_id = uuid4()
    email = "test@example.com"

    with patch.object(service, "delete_user_storage_files", return_value=True):
        with patch.object(service, "delete_user_from_auth", return_value=True):
            with patch.object(service, "send_deletion_confirmation_email", return_value=True):
                result = await service.delete_user_account(user_id, email)

                assert result.success is True
                assert result.storage_deleted is True
                assert result.auth_deleted is True
                assert result.email_sent is True
                assert result.error is None


@pytest.mark.asyncio
async def test_delete_user_account_auth_failure_returns_failure(mock_settings):
    """Account deletion fails when auth deletion fails."""
    service = UserDeletionService(mock_settings)
    user_id = uuid4()
    email = "test@example.com"

    with patch.object(service, "delete_user_storage_files", return_value=True):
        with patch.object(service, "delete_user_from_auth", return_value=False):
            result = await service.delete_user_account(user_id, email)

            assert result.success is False
            assert result.auth_deleted is False
            assert result.error is not None


@pytest.mark.asyncio
async def test_delete_user_account_storage_failure_continues(mock_settings):
    """Account deletion continues when storage deletion fails."""
    service = UserDeletionService(mock_settings)
    user_id = uuid4()
    email = "test@example.com"

    with patch.object(service, "delete_user_storage_files", return_value=False):
        with patch.object(service, "delete_user_from_auth", return_value=True):
            with patch.object(service, "send_deletion_confirmation_email", return_value=True):
                result = await service.delete_user_account(user_id, email)

                # Storage failure is non-blocking
                assert result.success is True
                assert result.storage_deleted is False
                assert result.auth_deleted is True


# =============================================================================
# Tests for DELETE /api/user/me endpoint
# =============================================================================


@pytest.mark.asyncio
async def test_delete_user_me_requires_auth(test_client: AsyncClient):
    """DELETE /api/user/me requires authentication."""
    response = await test_client.delete("/api/user/me")

    assert response.status_code == 401
    data = response.json()
    assert data["detail"]["code"] == AuthErrorCode.MISSING_AUTH


@pytest.mark.asyncio
async def test_delete_user_me_invalid_token_returns_401(test_client: AsyncClient):
    """DELETE /api/user/me with invalid token returns 401."""
    response = await test_client.delete(
        "/api/user/me",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_user_me_returns_202_on_success(test_client: AsyncClient):
    """DELETE /api/user/me returns 202 on successful deletion."""
    token = create_test_token()

    with patch(
        "app.routers.user.UserDeletionService.delete_user_account",
        new_callable=AsyncMock,
    ) as mock_delete:
        mock_delete.return_value = DeletionResult(
            success=True,
            storage_deleted=True,
            auth_deleted=True,
            email_sent=True,
        )

        response = await test_client.delete(
            "/api/user/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["message"] == "Account deletion initiated"
        assert data["confirmation_email_sent"] is True
        assert "deletion_scheduled_at" in data


@pytest.mark.asyncio
async def test_delete_user_me_returns_500_on_failure(test_client: AsyncClient):
    """DELETE /api/user/me returns 500 on deletion failure."""
    token = create_test_token()

    with patch(
        "app.routers.user.UserDeletionService.delete_user_account",
        new_callable=AsyncMock,
    ) as mock_delete:
        mock_delete.return_value = DeletionResult(
            success=False,
            storage_deleted=True,
            auth_deleted=False,
            email_sent=False,
            error="Auth deletion failed",
        )

        response = await test_client.delete(
            "/api/user/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 500
        data = response.json()
        assert data["detail"]["code"] == DeletionErrorCode.DELETION_FAILED


@pytest.mark.asyncio
async def test_delete_user_me_expired_token_returns_401(test_client: AsyncClient):
    """DELETE /api/user/me with expired token returns 401."""
    token = create_test_token(expires_in=-3600)  # Expired 1 hour ago

    response = await test_client.delete(
        "/api/user/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    data = response.json()
    assert data["detail"]["code"] == AuthErrorCode.TOKEN_EXPIRED
