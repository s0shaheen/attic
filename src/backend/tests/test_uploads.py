"""Tests for upload functionality including presigned URL generation."""

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

from app.core.config import Settings
from app.models.auth import AuthErrorCode
from app.routers.uploads import router as uploads_router
from app.schemas.uploads import UploadErrorCode
from app.services.storage import (
    MAX_FILE_SIZE_BYTES,
    PRESIGNED_URL_EXPIRY_SECONDS,
    PresignedUrlResult,
    SupabaseStorageService,
)
from app.services.uploads import (
    ALLOWED_CONTENT_TYPES,
    TIER_UPLOAD_LIMITS,
    UploadService,
)

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
    """Create a test FastAPI app with upload routes."""
    app = FastAPI()
    app.include_router(uploads_router)
    return app


@pytest.fixture
async def test_client():
    """Create test client with upload routes."""
    app = create_test_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    return Settings(
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


# =============================================================================
# Tests for SupabaseStorageService
# =============================================================================


@pytest.mark.asyncio
async def test_storage_service_generates_correct_path(mock_settings):
    """Storage path follows {user_id}/{upload_id}.zip convention."""
    service = SupabaseStorageService(mock_settings)
    user_id = uuid4()
    upload_id = uuid4()

    path = service._get_storage_path(user_id, upload_id)

    assert path == f"{user_id}/{upload_id}.zip"


@pytest.mark.asyncio
async def test_storage_service_presigned_url_success(mock_settings):
    """Presigned URL generation returns URL on success."""
    service = SupabaseStorageService(mock_settings)
    user_id = uuid4()
    upload_id = uuid4()

    mock_response = Response(
        status_code=200,
        json={"url": "/storage/v1/object/upload/signed/test-token"},
    )

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await service.create_presigned_upload_url(user_id, upload_id)

        assert result.success is True
        assert result.presigned_url is not None
        assert TEST_SUPABASE_URL in result.presigned_url


@pytest.mark.asyncio
async def test_storage_service_presigned_url_with_signedURL_key(mock_settings):
    """Presigned URL generation handles signedURL response key."""
    service = SupabaseStorageService(mock_settings)
    user_id = uuid4()
    upload_id = uuid4()

    mock_response = Response(
        status_code=200,
        json={"signedURL": "https://full-url.com/signed-token"},
    )

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await service.create_presigned_upload_url(user_id, upload_id)

        assert result.success is True
        assert result.presigned_url == "https://full-url.com/signed-token"


@pytest.mark.asyncio
async def test_storage_service_presigned_url_failure(mock_settings):
    """Presigned URL generation returns error on failure."""
    service = SupabaseStorageService(mock_settings)
    user_id = uuid4()
    upload_id = uuid4()

    mock_response = Response(status_code=500, text="Internal Server Error")

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await service.create_presigned_upload_url(user_id, upload_id)

        assert result.success is False
        assert result.error is not None
        assert "500" in result.error


@pytest.mark.asyncio
async def test_storage_service_presigned_url_timeout(mock_settings):
    """Presigned URL generation handles timeout gracefully."""
    import httpx

    service = SupabaseStorageService(mock_settings)
    user_id = uuid4()
    upload_id = uuid4()

    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("timeout")):
        result = await service.create_presigned_upload_url(user_id, upload_id)

        assert result.success is False
        assert "timed out" in result.error.lower()


@pytest.mark.asyncio
async def test_storage_service_presigned_url_missing_url_in_response(mock_settings):
    """Presigned URL generation handles missing URL in response."""
    service = SupabaseStorageService(mock_settings)
    user_id = uuid4()
    upload_id = uuid4()

    mock_response = Response(
        status_code=200,
        json={"some_other_key": "value"},
    )

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await service.create_presigned_upload_url(user_id, upload_id)

        assert result.success is False
        assert "invalid response" in result.error.lower()


def test_storage_service_expiry_is_one_hour(mock_settings):
    """Presigned URL expiry is approximately 1 hour from now."""
    from datetime import UTC, datetime, timedelta

    service = SupabaseStorageService(mock_settings)

    expiry = service.get_presigned_url_expiry()
    expected = datetime.now(UTC) + timedelta(seconds=PRESIGNED_URL_EXPIRY_SECONDS)

    # Allow 1 second tolerance
    assert abs((expiry - expected).total_seconds()) < 1


# =============================================================================
# Tests for UploadService
# =============================================================================


@pytest.mark.asyncio
async def test_upload_service_valid_content_types():
    """Upload service accepts valid ZIP content types."""
    assert "application/zip" in ALLOWED_CONTENT_TYPES
    assert "application/x-zip-compressed" in ALLOWED_CONTENT_TYPES
    assert "application/octet-stream" in ALLOWED_CONTENT_TYPES


@pytest.mark.asyncio
async def test_upload_service_rejects_invalid_content_type(mock_settings):
    """Upload service rejects non-ZIP content types."""
    service = UploadService(mock_settings)
    user_id = uuid4()

    result = await service.create_presigned_url(
        user_id=user_id,
        filename="test.pdf",
        content_type="application/pdf",
        user_tier="free",
        current_upload_count=0,
    )

    assert result.success is False
    assert result.error_code == "INVALID_CONTENT_TYPE"
    assert "pdf" in result.error.lower()


@pytest.mark.asyncio
async def test_upload_service_accepts_zip_content_type(mock_settings):
    """Upload service accepts application/zip content type."""
    service = UploadService(mock_settings)
    user_id = uuid4()

    mock_url_result = PresignedUrlResult(
        success=True,
        presigned_url="https://example.com/upload",
    )

    with patch.object(
        service.storage_service, "create_presigned_upload_url", return_value=mock_url_result
    ):
        result = await service.create_presigned_url(
            user_id=user_id,
            filename="test.zip",
            content_type="application/zip",
            user_tier="free",
            current_upload_count=0,
        )

        assert result.success is True


@pytest.mark.asyncio
async def test_upload_service_free_tier_first_upload_allowed(mock_settings):
    """Free tier user with 0 uploads can upload."""
    service = UploadService(mock_settings)
    user_id = uuid4()

    mock_url_result = PresignedUrlResult(
        success=True,
        presigned_url="https://example.com/upload",
    )

    with patch.object(
        service.storage_service, "create_presigned_upload_url", return_value=mock_url_result
    ):
        result = await service.create_presigned_url(
            user_id=user_id,
            filename="test.zip",
            content_type="application/zip",
            user_tier="free",
            current_upload_count=0,
        )

        assert result.success is True


@pytest.mark.asyncio
async def test_upload_service_free_tier_second_upload_blocked(mock_settings):
    """Free tier user with 1 upload cannot upload another."""
    service = UploadService(mock_settings)
    user_id = uuid4()

    result = await service.create_presigned_url(
        user_id=user_id,
        filename="test.zip",
        content_type="application/zip",
        user_tier="free",
        current_upload_count=1,
    )

    assert result.success is False
    assert result.error_code == "UPLOAD_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_upload_service_paid_tier_unlimited_uploads(mock_settings):
    """Paid tier users have unlimited uploads."""
    service = UploadService(mock_settings)
    user_id = uuid4()

    mock_url_result = PresignedUrlResult(
        success=True,
        presigned_url="https://example.com/upload",
    )

    for tier in ["explorer", "expert", "pioneer"]:
        with patch.object(
            service.storage_service, "create_presigned_upload_url", return_value=mock_url_result
        ):
            result = await service.create_presigned_url(
                user_id=user_id,
                filename="test.zip",
                content_type="application/zip",
                user_tier=tier,
                current_upload_count=100,  # Many existing uploads
            )

            assert result.success is True, f"Tier {tier} should allow uploads"


@pytest.mark.asyncio
async def test_upload_service_returns_correct_metadata(mock_settings):
    """Upload service returns all required metadata."""
    service = UploadService(mock_settings)
    user_id = uuid4()

    mock_url_result = PresignedUrlResult(
        success=True,
        presigned_url="https://example.com/upload",
    )

    with patch.object(
        service.storage_service, "create_presigned_upload_url", return_value=mock_url_result
    ):
        result = await service.create_presigned_url(
            user_id=user_id,
            filename="test.zip",
            content_type="application/zip",
            user_tier="free",
            current_upload_count=0,
        )

        assert result.success is True
        assert result.upload_id is not None
        assert result.presigned_url is not None
        assert result.storage_path is not None
        assert result.expires_at is not None
        assert result.max_file_size == MAX_FILE_SIZE_BYTES


@pytest.mark.asyncio
async def test_upload_service_storage_path_contains_user_id(mock_settings):
    """Storage path contains user_id from JWT, not client input."""
    service = UploadService(mock_settings)
    user_id = uuid4()

    mock_url_result = PresignedUrlResult(
        success=True,
        presigned_url="https://example.com/upload",
    )

    with patch.object(
        service.storage_service, "create_presigned_upload_url", return_value=mock_url_result
    ):
        result = await service.create_presigned_url(
            user_id=user_id,
            filename="test.zip",
            content_type="application/zip",
            user_tier="free",
            current_upload_count=0,
        )

        assert str(user_id) in result.storage_path


@pytest.mark.asyncio
async def test_upload_service_handles_storage_error(mock_settings):
    """Upload service handles storage service errors."""
    service = UploadService(mock_settings)
    user_id = uuid4()

    mock_url_result = PresignedUrlResult(
        success=False,
        error="Storage connection failed",
    )

    with patch.object(
        service.storage_service, "create_presigned_upload_url", return_value=mock_url_result
    ):
        result = await service.create_presigned_url(
            user_id=user_id,
            filename="test.zip",
            content_type="application/zip",
            user_tier="free",
            current_upload_count=0,
        )

        assert result.success is False
        assert result.error_code == "STORAGE_ERROR"


# =============================================================================
# Tests for POST /api/uploads/presigned-url endpoint
# =============================================================================


@pytest.mark.asyncio
async def test_presigned_url_endpoint_requires_auth(test_client: AsyncClient):
    """POST /api/uploads/presigned-url requires authentication."""
    response = await test_client.post(
        "/api/uploads/presigned-url",
        json={"filename": "test.zip", "content_type": "application/zip"},
    )

    assert response.status_code == 401
    data = response.json()
    assert data["detail"]["code"] == AuthErrorCode.MISSING_AUTH


@pytest.mark.asyncio
async def test_presigned_url_endpoint_invalid_token_returns_401(test_client: AsyncClient):
    """POST /api/uploads/presigned-url with invalid token returns 401."""
    response = await test_client.post(
        "/api/uploads/presigned-url",
        json={"filename": "test.zip", "content_type": "application/zip"},
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_presigned_url_endpoint_expired_token_returns_401(test_client: AsyncClient):
    """POST /api/uploads/presigned-url with expired token returns 401."""
    token = create_test_token(expires_in=-3600)

    response = await test_client.post(
        "/api/uploads/presigned-url",
        json={"filename": "test.zip", "content_type": "application/zip"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    data = response.json()
    assert data["detail"]["code"] == AuthErrorCode.TOKEN_EXPIRED


@pytest.mark.asyncio
async def test_presigned_url_endpoint_success(test_client: AsyncClient):
    """POST /api/uploads/presigned-url returns 200 on success."""
    token = create_test_token()

    with patch(
        "app.routers.uploads.UploadService.create_presigned_url",
        new_callable=AsyncMock,
    ) as mock_create:
        from datetime import UTC, datetime
        from uuid import uuid4

        mock_upload_id = uuid4()
        mock_create.return_value = type(
            "CreatePresignedUrlResult",
            (),
            {
                "success": True,
                "upload_id": mock_upload_id,
                "presigned_url": "https://example.com/upload",
                "storage_path": f"tiktok-exports/{TEST_USER_ID}/{mock_upload_id}.zip",
                "expires_at": datetime.now(UTC),
                "max_file_size": MAX_FILE_SIZE_BYTES,
            },
        )()

        response = await test_client.post(
            "/api/uploads/presigned-url",
            json={"filename": "test.zip", "content_type": "application/zip"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "upload_id" in data
        assert "presigned_url" in data
        assert "storage_path" in data
        assert "expires_at" in data
        assert "max_file_size" in data
        assert data["presigned_url"] == "https://example.com/upload"


@pytest.mark.asyncio
async def test_presigned_url_endpoint_invalid_content_type_returns_400(test_client: AsyncClient):
    """POST /api/uploads/presigned-url with invalid content type returns 400."""
    token = create_test_token()

    with patch(
        "app.routers.uploads.UploadService.create_presigned_url",
        new_callable=AsyncMock,
    ) as mock_create:
        mock_create.return_value = type(
            "CreatePresignedUrlResult",
            (),
            {
                "success": False,
                "error": "Invalid content type: application/pdf",
                "error_code": UploadErrorCode.INVALID_CONTENT_TYPE,
            },
        )()

        response = await test_client.post(
            "/api/uploads/presigned-url",
            json={"filename": "test.pdf", "content_type": "application/pdf"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["code"] == UploadErrorCode.INVALID_CONTENT_TYPE


@pytest.mark.asyncio
async def test_presigned_url_endpoint_upload_limit_returns_403(test_client: AsyncClient):
    """POST /api/uploads/presigned-url returns 403 when limit exceeded."""
    token = create_test_token()

    with patch(
        "app.routers.uploads.UploadService.create_presigned_url",
        new_callable=AsyncMock,
    ) as mock_create:
        mock_create.return_value = type(
            "CreatePresignedUrlResult",
            (),
            {
                "success": False,
                "error": "Upload limit reached",
                "error_code": UploadErrorCode.UPLOAD_LIMIT_EXCEEDED,
            },
        )()

        response = await test_client.post(
            "/api/uploads/presigned-url",
            json={"filename": "test.zip", "content_type": "application/zip"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403
        data = response.json()
        assert data["detail"]["code"] == UploadErrorCode.UPLOAD_LIMIT_EXCEEDED


@pytest.mark.asyncio
async def test_presigned_url_endpoint_storage_error_returns_500(test_client: AsyncClient):
    """POST /api/uploads/presigned-url returns 500 on storage error."""
    token = create_test_token()

    with patch(
        "app.routers.uploads.UploadService.create_presigned_url",
        new_callable=AsyncMock,
    ) as mock_create:
        mock_create.return_value = type(
            "CreatePresignedUrlResult",
            (),
            {
                "success": False,
                "error": "Storage service unavailable",
                "error_code": UploadErrorCode.STORAGE_ERROR,
            },
        )()

        response = await test_client.post(
            "/api/uploads/presigned-url",
            json={"filename": "test.zip", "content_type": "application/zip"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 500
        data = response.json()
        assert data["detail"]["code"] == UploadErrorCode.STORAGE_ERROR


@pytest.mark.asyncio
async def test_presigned_url_endpoint_missing_filename_returns_422(test_client: AsyncClient):
    """POST /api/uploads/presigned-url with missing filename returns 422."""
    token = create_test_token()

    response = await test_client.post(
        "/api/uploads/presigned-url",
        json={"content_type": "application/zip"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_presigned_url_endpoint_empty_filename_returns_422(test_client: AsyncClient):
    """POST /api/uploads/presigned-url with empty filename returns 422."""
    token = create_test_token()

    response = await test_client.post(
        "/api/uploads/presigned-url",
        json={"filename": "", "content_type": "application/zip"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_presigned_url_endpoint_default_content_type(test_client: AsyncClient):
    """POST /api/uploads/presigned-url uses default content type if not provided."""
    token = create_test_token()

    with patch(
        "app.routers.uploads.UploadService.create_presigned_url",
        new_callable=AsyncMock,
    ) as mock_create:
        from datetime import UTC, datetime
        from uuid import uuid4

        mock_upload_id = uuid4()
        mock_create.return_value = type(
            "CreatePresignedUrlResult",
            (),
            {
                "success": True,
                "upload_id": mock_upload_id,
                "presigned_url": "https://example.com/upload",
                "storage_path": f"tiktok-exports/{TEST_USER_ID}/{mock_upload_id}.zip",
                "expires_at": datetime.now(UTC),
                "max_file_size": MAX_FILE_SIZE_BYTES,
            },
        )()

        response = await test_client.post(
            "/api/uploads/presigned-url",
            json={"filename": "test.zip"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        # Verify the service was called with default content type
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["content_type"] == "application/zip"


@pytest.mark.asyncio
async def test_presigned_url_endpoint_user_id_from_token(test_client: AsyncClient):
    """POST /api/uploads/presigned-url uses user_id from JWT, not client."""
    from uuid import UUID

    test_user_id = str(uuid4())
    token = create_test_token(user_id=test_user_id)

    with patch(
        "app.routers.uploads.UploadService.create_presigned_url",
        new_callable=AsyncMock,
    ) as mock_create:
        from datetime import UTC, datetime

        mock_upload_id = uuid4()
        mock_create.return_value = type(
            "CreatePresignedUrlResult",
            (),
            {
                "success": True,
                "upload_id": mock_upload_id,
                "presigned_url": "https://example.com/upload",
                "storage_path": f"tiktok-exports/{test_user_id}/{mock_upload_id}.zip",
                "expires_at": datetime.now(UTC),
                "max_file_size": MAX_FILE_SIZE_BYTES,
            },
        )()

        response = await test_client.post(
            "/api/uploads/presigned-url",
            json={"filename": "test.zip", "content_type": "application/zip"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        # Verify the service was called with user_id from token
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["user_id"] == UUID(test_user_id)


# =============================================================================
# Tests for tier limits configuration
# =============================================================================


def test_tier_upload_limits_configured():
    """Tier upload limits are properly configured."""
    assert TIER_UPLOAD_LIMITS["free"] == 1
    assert TIER_UPLOAD_LIMITS["explorer"] is None  # Unlimited
    assert TIER_UPLOAD_LIMITS["expert"] is None  # Unlimited
    assert TIER_UPLOAD_LIMITS["pioneer"] is None  # Unlimited


def test_max_file_size_is_500mb():
    """Max file size is 500MB as per PRD."""
    assert MAX_FILE_SIZE_BYTES == 524288000  # 500 * 1024 * 1024


def test_presigned_url_expiry_is_one_hour():
    """Presigned URL expiry is 3600 seconds (1 hour)."""
    assert PRESIGNED_URL_EXPIRY_SECONDS == 3600
