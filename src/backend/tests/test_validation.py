"""Tests for upload validation service.

This module contains comprehensive tests for the validation service including:
- Valid ZIP detection
- TikTok export structure validation
- Error code mapping
- Hash generation
"""

import io
import json
import os
import time
import zipfile
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
from httpx import ASGITransport, AsyncClient

from app.schemas.uploads import ValidationErrorCode
from app.services.validation import ValidationService

# Test configuration
TEST_JWT_SECRET = "test-jwt-secret-for-testing-only"
TEST_SUPABASE_URL = "https://test-project.supabase.co"
TEST_USER_ID = str(uuid4())
TEST_UPLOAD_ID = uuid4()


def create_test_zip(files: dict[str, str | bytes]) -> bytes:
    """Create an in-memory ZIP file with the given files.

    Args:
        files: Dictionary mapping file paths to their content

    Returns:
        Bytes of the ZIP file
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            if isinstance(content, str):
                zf.writestr(path, content)
            else:
                zf.writestr(path, content)
    buffer.seek(0)
    return buffer.read()


def create_valid_tiktok_export(liked_count: int = 5, favorited_count: int = 3) -> bytes:
    """Create a valid TikTok export ZIP with specified counts.

    Args:
        liked_count: Number of liked videos to include
        favorited_count: Number of favorited videos to include

    Returns:
        Bytes of the ZIP file
    """
    liked_videos = [
        {"date": f"2025-01-{i:02d} 12:00:00", "link": f"https://example.com/v{i}"}
        for i in range(1, liked_count + 1)
    ]
    favorited_videos = [
        {"Date": f"2025-02-{i:02d} 12:00:00", "Link": f"https://example.com/fav{i}"}
        for i in range(1, favorited_count + 1)
    ]

    files = {
        "Activity/Like List.json": json.dumps({"Like List": {"ItemFavoriteList": liked_videos}}),
        "Activity/Favorite Videos.json": json.dumps(
            {"Favorite Videos": {"FavoriteVideoList": favorited_videos}}
        ),
    }
    return create_test_zip(files)


def create_test_token(
    user_id: str = TEST_USER_ID,
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
        "email": "test@example.com",
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


# =============================================================================
# ValidationService Unit Tests
# =============================================================================


class TestValidationServiceZipValidation:
    """Tests for ZIP file validation."""

    @pytest.fixture
    def service(self):
        return ValidationService()

    def test_is_valid_zip_with_valid_zip(self, service):
        """Valid ZIP file returns True."""
        zip_content = create_test_zip({"test.txt": "hello"})
        assert service._is_valid_zip(zip_content) is True

    def test_is_valid_zip_with_invalid_content(self, service):
        """Non-ZIP content returns False."""
        assert service._is_valid_zip(b"not a zip file") is False
        assert service._is_valid_zip(b"") is False
        assert service._is_valid_zip(b"PK") is False  # Partial ZIP header

    def test_is_corrupted_zip_with_valid_zip(self, service):
        """Valid ZIP returns False (not corrupted)."""
        zip_content = create_test_zip({"test.txt": "hello"})
        assert service._is_corrupted_zip(zip_content) is False

    def test_is_corrupted_zip_with_corrupted_content(self, service):
        """Corrupted ZIP returns True."""
        # Create a valid ZIP then corrupt it
        zip_content = create_test_zip({"test.txt": "hello"})
        corrupted = zip_content[:-10]  # Truncate
        assert service._is_corrupted_zip(corrupted) is True


class TestValidationServiceHashComputation:
    """Tests for file hash computation."""

    @pytest.fixture
    def service(self):
        return ValidationService()

    def test_compute_file_hash_returns_sha256(self, service):
        """Hash is a valid SHA256 hex string."""
        content = b"test content"
        file_hash = service._compute_file_hash(content)

        assert isinstance(file_hash, str)
        assert len(file_hash) == 64  # SHA256 produces 64 hex chars
        assert all(c in "0123456789abcdef" for c in file_hash)

    def test_compute_file_hash_is_deterministic(self, service):
        """Same content produces same hash."""
        content = b"test content"
        hash1 = service._compute_file_hash(content)
        hash2 = service._compute_file_hash(content)
        assert hash1 == hash2

    def test_compute_file_hash_different_for_different_content(self, service):
        """Different content produces different hash."""
        hash1 = service._compute_file_hash(b"content 1")
        hash2 = service._compute_file_hash(b"content 2")
        assert hash1 != hash2


class TestValidationServiceValidateUpload:
    """Tests for the main validate_upload method."""

    @pytest.fixture
    def service(self):
        return ValidationService()

    @pytest.mark.asyncio
    async def test_validate_valid_export_returns_valid(self, service):
        """Valid TikTok export passes validation."""
        zip_content = create_valid_tiktok_export(liked_count=5, favorited_count=3)

        result = await service.validate_upload(
            upload_id=TEST_UPLOAD_ID,
            user_id=uuid4(),
            file_content=zip_content,
        )

        assert result.result.valid is True
        assert result.result.error_code is None
        assert result.result.error_message is None
        assert result.result.liked_count == 5
        assert result.result.favorited_count == 3
        assert result.result.file_hash is not None
        assert result.should_update_status is True
        assert result.new_status == "validated"

    @pytest.mark.asyncio
    async def test_validate_invalid_zip_returns_invalid_file(self, service):
        """Non-ZIP file returns INVALID_FILE error."""
        result = await service.validate_upload(
            upload_id=TEST_UPLOAD_ID,
            user_id=uuid4(),
            file_content=b"not a zip file",
        )

        assert result.result.valid is False
        assert result.result.error_code == ValidationErrorCode.INVALID_FILE
        assert result.result.error_message is not None
        assert result.should_update_status is True
        assert result.new_status == "invalid"

    @pytest.mark.asyncio
    async def test_validate_corrupted_zip_returns_error(self, service):
        """Corrupted/truncated ZIP returns an appropriate error.

        A truncated ZIP may be detected as either INVALID_FILE (if completely
        unreadable) or FILE_CORRUPTED (if readable but fails CRC checks).
        Both are acceptable error codes for this scenario.
        """
        zip_content = create_valid_tiktok_export()
        corrupted = zip_content[:-10]  # Truncate to corrupt

        result = await service.validate_upload(
            upload_id=TEST_UPLOAD_ID,
            user_id=uuid4(),
            file_content=corrupted,
        )

        assert result.result.valid is False
        # Either error code is acceptable for corrupted/truncated files
        assert result.result.error_code in (
            ValidationErrorCode.INVALID_FILE,
            ValidationErrorCode.FILE_CORRUPTED,
        )
        assert result.should_update_status is True
        assert result.new_status == "invalid"

    @pytest.mark.asyncio
    async def test_validate_wrong_structure_returns_invalid_export(self, service):
        """ZIP without TikTok export structure returns INVALID_EXPORT."""
        zip_content = create_test_zip(
            {
                "README.txt": "This is not a TikTok export",
                "some_data.json": json.dumps({"foo": "bar"}),
            }
        )

        result = await service.validate_upload(
            upload_id=TEST_UPLOAD_ID,
            user_id=uuid4(),
            file_content=zip_content,
        )

        assert result.result.valid is False
        assert result.result.error_code == ValidationErrorCode.INVALID_EXPORT
        assert result.should_update_status is True
        assert result.new_status == "invalid"

    @pytest.mark.asyncio
    async def test_validate_empty_export_returns_empty_export(self, service):
        """TikTok export with no videos returns EMPTY_EXPORT."""
        zip_content = create_test_zip(
            {
                "Activity/Like List.json": json.dumps({"Like List": {"ItemFavoriteList": []}}),
                "Activity/Favorite Videos.json": json.dumps(
                    {"Favorite Videos": {"FavoriteVideoList": []}}
                ),
            }
        )

        result = await service.validate_upload(
            upload_id=TEST_UPLOAD_ID,
            user_id=uuid4(),
            file_content=zip_content,
        )

        assert result.result.valid is False
        assert result.result.error_code == ValidationErrorCode.EMPTY_EXPORT
        assert result.should_update_status is True
        assert result.new_status == "invalid"

    @pytest.mark.asyncio
    async def test_validate_txt_format_returns_unsupported(self, service):
        """TXT format export (instead of JSON) returns UNSUPPORTED_FORMAT."""
        # Create a ZIP with TXT content that looks like it might be TikTok data
        # but in wrong format
        zip_content = create_test_zip(
            {
                "Activity/Like List.json": "Date\tLink\n2025-01-01\thttps://example.com",
            }
        )

        result = await service.validate_upload(
            upload_id=TEST_UPLOAD_ID,
            user_id=uuid4(),
            file_content=zip_content,
        )

        assert result.result.valid is False
        assert result.result.error_code == ValidationErrorCode.UNSUPPORTED_FORMAT
        assert result.should_update_status is True
        assert result.new_status == "invalid"

    @pytest.mark.asyncio
    async def test_validate_returns_file_hash(self, service):
        """Validation always returns file hash."""
        zip_content = create_valid_tiktok_export()

        result = await service.validate_upload(
            upload_id=TEST_UPLOAD_ID,
            user_id=uuid4(),
            file_content=zip_content,
        )

        assert result.result.file_hash is not None
        assert len(result.result.file_hash) == 64

    @pytest.mark.asyncio
    async def test_validate_returns_counts_on_success(self, service):
        """Successful validation returns liked and favorited counts."""
        zip_content = create_valid_tiktok_export(liked_count=10, favorited_count=5)

        result = await service.validate_upload(
            upload_id=TEST_UPLOAD_ID,
            user_id=uuid4(),
            file_content=zip_content,
        )

        assert result.result.valid is True
        assert result.result.liked_count == 10
        assert result.result.favorited_count == 5


class TestValidationServiceSecurityHandling:
    """Tests for security-related scenarios."""

    @pytest.fixture
    def service(self):
        return ValidationService()

    @pytest.mark.asyncio
    async def test_validate_path_traversal_returns_corrupted(self, service):
        """ZIP with path traversal is treated as corrupted (no security details)."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("../../../etc/passwd", "malicious content")
        buffer.seek(0)

        result = await service.validate_upload(
            upload_id=TEST_UPLOAD_ID,
            user_id=uuid4(),
            file_content=buffer.read(),
        )

        # Security errors are reported as FILE_CORRUPTED to not reveal details
        assert result.result.valid is False
        assert result.result.error_code == ValidationErrorCode.FILE_CORRUPTED
        # Error message should not reveal security details
        assert "security" not in result.result.error_message.lower()
        assert "traversal" not in result.result.error_message.lower()


# =============================================================================
# API Endpoint Tests
# =============================================================================


def create_test_app():
    """Create a test FastAPI app with upload routes."""
    from app.routers.uploads import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
async def test_client():
    """Create test client with upload routes."""
    app = create_test_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestValidateUploadEndpoint:
    """Tests for the POST /api/uploads/{upload_id}/validate endpoint."""

    @pytest.mark.asyncio
    async def test_validate_endpoint_requires_auth(self, test_client):
        """POST /api/uploads/{id}/validate requires authentication."""
        response = await test_client.post(
            f"/api/uploads/{TEST_UPLOAD_ID}/validate",
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_validate_endpoint_invalid_token_returns_401(self, test_client):
        """POST /api/uploads/{id}/validate with invalid token returns 401."""
        response = await test_client.post(
            f"/api/uploads/{TEST_UPLOAD_ID}/validate",
            headers={"Authorization": "Bearer invalid-token"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_validate_endpoint_expired_token_returns_401(self, test_client):
        """POST /api/uploads/{id}/validate with expired token returns 401."""
        token = create_test_token(expires_in=-3600)

        response = await test_client.post(
            f"/api/uploads/{TEST_UPLOAD_ID}/validate",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_validate_endpoint_invalid_uuid_returns_422(self, test_client):
        """POST /api/uploads/{id}/validate with invalid UUID returns 422."""
        token = create_test_token()

        response = await test_client.post(
            "/api/uploads/not-a-uuid/validate",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_validate_endpoint_not_found_returns_404(self, test_client):
        """POST /api/uploads/{id}/validate for unknown upload returns 404."""
        token = create_test_token()

        response = await test_client.post(
            f"/api/uploads/{TEST_UPLOAD_ID}/validate",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Currently returns 404 because database integration is pending
        assert response.status_code == 404


# =============================================================================
# Error Code Mapping Tests
# =============================================================================


class TestValidationErrorCodeMapping:
    """Tests for ValidationErrorCode enum."""

    def test_all_error_codes_exist(self):
        """All expected error codes are defined."""
        expected_codes = [
            "INVALID_FILE",
            "INVALID_EXPORT",
            "EMPTY_EXPORT",
            "FILE_TOO_LARGE",
            "FILE_CORRUPTED",
            "UNSUPPORTED_FORMAT",
        ]
        for code in expected_codes:
            assert hasattr(ValidationErrorCode, code)

    def test_error_codes_are_strings(self):
        """Error codes have string values."""
        assert ValidationErrorCode.INVALID_FILE.value == "INVALID_FILE"
        assert ValidationErrorCode.INVALID_EXPORT.value == "INVALID_EXPORT"
        assert ValidationErrorCode.EMPTY_EXPORT.value == "EMPTY_EXPORT"
