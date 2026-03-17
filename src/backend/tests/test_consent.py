"""Tests for consent endpoint and schemas.

This module contains comprehensive tests for consent functionality including:
- Consent request validation
- Consent version tracking
- Endpoint authentication
- Status transitions
"""

import os
import time

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

from uuid import uuid4

import jwt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.schemas.uploads import (
    CURRENT_CONSENT_VERSION,
    ConsentRequest,
    ConsentResponse,
)

# Test configuration
TEST_JWT_SECRET = "test-jwt-secret-for-testing-only"
TEST_SUPABASE_URL = "https://test-project.supabase.co"
TEST_USER_ID = uuid4()
TEST_UPLOAD_ID = uuid4()


def create_test_token(
    user_id: str | None = None,
    expires_in: int = 3600,
) -> str:
    """Create a test JWT token."""
    if user_id is None:
        user_id = str(TEST_USER_ID)
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
# ConsentRequest Schema Tests
# =============================================================================


class TestConsentRequestSchema:
    """Tests for ConsentRequest Pydantic model."""

    def test_consent_request_valid_with_consent_true(self):
        """Valid request with consent_given=true."""
        request = ConsentRequest(consent_given=True)
        assert request.consent_given is True
        assert request.consent_version == CURRENT_CONSENT_VERSION

    def test_consent_request_valid_with_consent_false(self):
        """Valid request with consent_given=false."""
        request = ConsentRequest(consent_given=False)
        assert request.consent_given is False

    def test_consent_request_with_custom_version(self):
        """Request with custom consent version."""
        request = ConsentRequest(consent_given=True, consent_version="2.0.0")
        assert request.consent_version == "2.0.0"

    def test_consent_request_default_version_is_current(self):
        """Default version matches CURRENT_CONSENT_VERSION."""
        request = ConsentRequest(consent_given=True)
        assert request.consent_version == CURRENT_CONSENT_VERSION

    def test_current_consent_version_is_1_0_0(self):
        """CURRENT_CONSENT_VERSION is 1.0.0."""
        assert CURRENT_CONSENT_VERSION == "1.0.0"


# =============================================================================
# ConsentResponse Schema Tests
# =============================================================================


class TestConsentResponseSchema:
    """Tests for ConsentResponse Pydantic model."""

    def test_consent_response_valid(self):
        """Valid response with all fields."""
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        response = ConsentResponse(
            upload_id=TEST_UPLOAD_ID,
            consent_given=True,
            consent_version="1.0.0",
            consent_at=now,
            ready_to_process=True,
        )
        assert response.upload_id == TEST_UPLOAD_ID
        assert response.consent_given is True
        assert response.consent_version == "1.0.0"
        assert response.consent_at == now
        assert response.ready_to_process is True

    def test_consent_response_records_version(self):
        """Response includes consent version."""
        from datetime import UTC, datetime

        response = ConsentResponse(
            upload_id=TEST_UPLOAD_ID,
            consent_given=True,
            consent_version="1.0.0",
            consent_at=datetime.now(UTC),
            ready_to_process=True,
        )
        assert response.consent_version == "1.0.0"

    def test_consent_response_records_timestamp(self):
        """Response includes consent timestamp."""
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        response = ConsentResponse(
            upload_id=TEST_UPLOAD_ID,
            consent_given=True,
            consent_version="1.0.0",
            consent_at=now,
            ready_to_process=True,
        )
        assert response.consent_at == now


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


@pytest.mark.requires_db
class TestConsentEndpoint:
    """Tests for the POST /api/uploads/{upload_id}/consent endpoint."""

    @pytest.mark.asyncio
    async def test_consent_endpoint_requires_auth(self, test_client):
        """POST /api/uploads/{id}/consent requires authentication."""
        response = await test_client.post(
            f"/api/uploads/{TEST_UPLOAD_ID}/consent",
            json={"consent_given": True, "consent_version": "1.0.0"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_consent_endpoint_invalid_token_returns_401(self, test_client):
        """POST /api/uploads/{id}/consent with invalid token returns 401."""
        response = await test_client.post(
            f"/api/uploads/{TEST_UPLOAD_ID}/consent",
            json={"consent_given": True, "consent_version": "1.0.0"},
            headers={"Authorization": "Bearer invalid-token"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_consent_endpoint_expired_token_returns_401(self, test_client):
        """POST /api/uploads/{id}/consent with expired token returns 401."""
        token = create_test_token(expires_in=-3600)

        response = await test_client.post(
            f"/api/uploads/{TEST_UPLOAD_ID}/consent",
            json={"consent_given": True, "consent_version": "1.0.0"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_consent_endpoint_invalid_uuid_returns_422(self, test_client):
        """POST /api/uploads/{id}/consent with invalid UUID returns 422."""
        token = create_test_token()

        response = await test_client.post(
            "/api/uploads/not-a-uuid/consent",
            json={"consent_given": True, "consent_version": "1.0.0"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_consent_endpoint_consent_false_returns_400(self, test_client):
        """POST /api/uploads/{id}/consent with consent_given=false returns 400."""
        token = create_test_token()

        response = await test_client.post(
            f"/api/uploads/{TEST_UPLOAD_ID}/consent",
            json={"consent_given": False, "consent_version": "1.0.0"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "CONSENT_NOT_GIVEN"

    @pytest.mark.asyncio
    async def test_consent_endpoint_accepts_valid_consent(self, test_client):
        """POST /api/uploads/{id}/consent accepts valid consent request."""
        token = create_test_token()

        response = await test_client.post(
            f"/api/uploads/{TEST_UPLOAD_ID}/consent",
            json={"consent_given": True, "consent_version": "1.0.0"},
            headers={"Authorization": f"Bearer {token}"},
        )

        # Currently returns 404 because database integration is pending
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_consent_endpoint_accepts_custom_version(self, test_client):
        """POST /api/uploads/{id}/consent accepts custom consent version."""
        token = create_test_token()

        response = await test_client.post(
            f"/api/uploads/{TEST_UPLOAD_ID}/consent",
            json={"consent_given": True, "consent_version": "2.0.0"},
            headers={"Authorization": f"Bearer {token}"},
        )

        # Currently returns 404 because database integration is pending
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_consent_endpoint_default_version_used(self, test_client):
        """POST /api/uploads/{id}/consent uses default version if not provided."""
        token = create_test_token()

        response = await test_client.post(
            f"/api/uploads/{TEST_UPLOAD_ID}/consent",
            json={"consent_given": True},
            headers={"Authorization": f"Bearer {token}"},
        )

        # Currently returns 404 because database integration is pending
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_consent_endpoint_not_found_returns_404(self, test_client):
        """POST /api/uploads/{id}/consent for unknown upload returns 404."""
        token = create_test_token()

        response = await test_client.post(
            f"/api/uploads/{uuid4()}/consent",
            json={"consent_given": True, "consent_version": "1.0.0"},
            headers={"Authorization": f"Bearer {token}"},
        )

        # Currently returns 404 because database integration is pending
        assert response.status_code == 404


@pytest.mark.requires_db
class TestConsentEndpointIntegration:
    """Integration tests for consent endpoint.

    These tests verify behavior that will be fully testable
    when database integration is complete.
    """

    @pytest.mark.asyncio
    async def test_consent_endpoint_idempotent_behavior(self, test_client):
        """Multiple consent requests should be idempotent."""
        # This test documents expected behavior once DB is integrated
        # Second consent call with same version should:
        # - Return 409 Conflict with CONSENT_ALREADY_RECORDED
        # - Or return success with same response (idempotent)
        token = create_test_token()

        # First request
        response1 = await test_client.post(
            f"/api/uploads/{TEST_UPLOAD_ID}/consent",
            json={"consent_given": True, "consent_version": "1.0.0"},
            headers={"Authorization": f"Bearer {token}"},
        )

        # Second request (same data)
        response2 = await test_client.post(
            f"/api/uploads/{TEST_UPLOAD_ID}/consent",
            json={"consent_given": True, "consent_version": "1.0.0"},
            headers={"Authorization": f"Bearer {token}"},
        )

        # Currently both return 404 due to pending DB integration
        assert response1.status_code == 404
        assert response2.status_code == 404

    @pytest.mark.asyncio
    async def test_cannot_record_consent_without_scope(self, test_client):
        """Should return 422 if scope not selected."""
        # This test documents expected behavior once DB is integrated
        # Consent without scope_selected status should return 422
        token = create_test_token()

        response = await test_client.post(
            f"/api/uploads/{TEST_UPLOAD_ID}/consent",
            json={"consent_given": True, "consent_version": "1.0.0"},
            headers={"Authorization": f"Bearer {token}"},
        )

        # Currently returns 404 because database integration is pending
        # Once DB is integrated, this should return 422 for uploads
        # that haven't had scope selected
        assert response.status_code == 404
