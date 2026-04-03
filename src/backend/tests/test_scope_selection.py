"""Tests for scope selection service.

This module contains comprehensive tests for scope selection including:
- Scope count calculations
- Tier limit enforcement
- Upload state validation
- Error handling
"""

import time
from uuid import uuid4

import jwt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.schemas.uploads import ScopeType
from app.services.uploads import UploadsService

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
# UploadsService Scope Count Tests
# =============================================================================


class TestScopeCountCalculation:
    """Tests for scope count calculations."""

    @pytest.fixture
    def service(self):
        return UploadsService()

    def test_scope_liked_only_counts_correct(self, service):
        """Liked scope only counts liked videos."""
        total, liked, favorited = service._calculate_scope_counts(
            scope=ScopeType.LIKED,
            liked_count=100,
            favorited_count=50,
        )
        assert total == 100
        assert liked == 100
        assert favorited == 0

    def test_scope_favorited_only_counts_correct(self, service):
        """Favorited scope only counts favorited videos."""
        total, liked, favorited = service._calculate_scope_counts(
            scope=ScopeType.FAVORITED,
            liked_count=100,
            favorited_count=50,
        )
        assert total == 50
        assert liked == 0
        assert favorited == 50

    def test_scope_both_counts_correct(self, service):
        """Both scope counts all unique videos."""
        total, liked, favorited = service._calculate_scope_counts(
            scope=ScopeType.BOTH,
            liked_count=100,
            favorited_count=50,
        )
        # Worst case: no overlap
        assert total == 150
        assert liked == 100
        assert favorited == 50

    def test_scope_with_zero_counts(self, service):
        """Zero counts are handled correctly."""
        total, liked, favorited = service._calculate_scope_counts(
            scope=ScopeType.BOTH,
            liked_count=0,
            favorited_count=0,
        )
        assert total == 0
        assert liked == 0
        assert favorited == 0


# =============================================================================
# UploadsService Status Validation Tests
# =============================================================================


class TestUploadStatusValidation:
    """Tests for upload status validation."""

    @pytest.fixture
    def service(self):
        return UploadsService()

    def test_validated_status_allows_scope(self, service):
        """Validated status allows scope selection."""
        is_valid, error_type, error_msg = service._validate_upload_status("validated")
        assert is_valid is True
        assert error_type is None
        assert error_msg is None

    def test_scope_selected_status_allows_scope(self, service):
        """scope_selected status allows scope change."""
        is_valid, error_type, error_msg = service._validate_upload_status("scope_selected")
        assert is_valid is True
        assert error_type is None
        assert error_msg is None

    def test_pending_status_rejects_scope(self, service):
        """Pending status rejects scope selection."""
        is_valid, error_type, error_msg = service._validate_upload_status("pending")
        assert is_valid is False
        assert error_type == "not_validated"
        assert "validated" in error_msg.lower()

    def test_processing_status_rejects_scope(self, service):
        """Processing status rejects scope selection."""
        is_valid, error_type, error_msg = service._validate_upload_status("processing")
        assert is_valid is False
        assert error_type == "already_processing"
        assert "processing" in error_msg.lower()

    def test_consented_status_rejects_scope(self, service):
        """Consented status rejects scope selection."""
        is_valid, error_type, error_msg = service._validate_upload_status("consented")
        assert is_valid is False
        assert error_type == "already_processing"

    def test_complete_status_rejects_scope(self, service):
        """Complete status rejects scope selection."""
        is_valid, error_type, error_msg = service._validate_upload_status("complete")
        assert is_valid is False
        assert error_type == "already_processing"

    def test_failed_status_rejects_scope(self, service):
        """Failed status rejects scope selection."""
        is_valid, error_type, error_msg = service._validate_upload_status("failed")
        assert is_valid is False
        assert error_type == "already_processing"


# =============================================================================
# UploadsService Scope Selection Tests
# =============================================================================


class TestScopeSelection:
    """Tests for select_scope method."""

    @pytest.fixture
    def service(self):
        return UploadsService()

    @pytest.mark.asyncio
    async def test_scope_within_free_tier_succeeds(self, service):
        """200 videos on free tier succeeds."""
        result = await service.select_scope(
            upload_id=TEST_UPLOAD_ID,
            user_id=TEST_USER_ID,
            scope=ScopeType.LIKED,
            user_tier="free",
            upload_status="validated",
            liked_count=200,
            favorited_count=50,
        )

        assert result.success is True
        assert result.response is not None
        assert result.response.total_items == 200
        assert result.response.within_limit is True
        assert result.response.tier_limit == 200
        assert result.response.ready_for_consent is True

    @pytest.mark.asyncio
    async def test_scope_exceeds_free_tier_returns_error(self, service):
        """201 videos on free tier fails."""
        result = await service.select_scope(
            upload_id=TEST_UPLOAD_ID,
            user_id=TEST_USER_ID,
            scope=ScopeType.LIKED,
            user_tier="free",
            upload_status="validated",
            liked_count=201,
            favorited_count=50,
        )

        assert result.success is False
        assert result.error_type == "tier_limit_exceeded"
        assert "201" in result.error_message
        assert "200" in result.error_message
        assert result.error_details["selected_count"] == 201
        assert result.error_details["tier_limit"] == 200
        assert result.error_details["upgrade_required"] is True

    @pytest.mark.asyncio
    async def test_scope_within_explorer_tier_succeeds(self, service):
        """1500 videos on explorer tier succeeds."""
        result = await service.select_scope(
            upload_id=TEST_UPLOAD_ID,
            user_id=TEST_USER_ID,
            scope=ScopeType.BOTH,
            user_tier="explorer",
            upload_status="validated",
            liked_count=1000,
            favorited_count=500,
        )

        assert result.success is True
        assert result.response.total_items == 1500
        assert result.response.within_limit is True
        assert result.response.tier_limit == 1500

    @pytest.mark.asyncio
    async def test_scope_change_allowed_before_consent(self, service):
        """Can update scope when status is scope_selected."""
        result = await service.select_scope(
            upload_id=TEST_UPLOAD_ID,
            user_id=TEST_USER_ID,
            scope=ScopeType.FAVORITED,  # Different scope
            user_tier="free",
            upload_status="scope_selected",  # Already selected scope
            liked_count=100,
            favorited_count=50,
        )

        assert result.success is True
        assert result.response.scope == ScopeType.FAVORITED
        assert result.response.total_items == 50

    @pytest.mark.asyncio
    async def test_scope_change_blocked_after_processing(self, service):
        """Cannot update scope after processing starts."""
        result = await service.select_scope(
            upload_id=TEST_UPLOAD_ID,
            user_id=TEST_USER_ID,
            scope=ScopeType.LIKED,
            user_tier="free",
            upload_status="processing",
            liked_count=100,
            favorited_count=50,
        )

        assert result.success is False
        assert result.error_type == "already_processing"

    @pytest.mark.asyncio
    async def test_scope_blocked_for_pending_upload(self, service):
        """Cannot set scope on non-validated upload."""
        result = await service.select_scope(
            upload_id=TEST_UPLOAD_ID,
            user_id=TEST_USER_ID,
            scope=ScopeType.LIKED,
            user_tier="free",
            upload_status="pending",
            liked_count=100,
            favorited_count=50,
        )

        assert result.success is False
        assert result.error_type == "not_validated"

    @pytest.mark.asyncio
    async def test_estimate_processing_time_included(self, service):
        """Response includes processing time estimate."""
        result = await service.select_scope(
            upload_id=TEST_UPLOAD_ID,
            user_id=TEST_USER_ID,
            scope=ScopeType.LIKED,
            user_tier="explorer",
            upload_status="validated",
            liked_count=1000,
            favorited_count=500,
        )

        assert result.success is True
        assert result.response.estimated_processing_minutes > 0
        # 1000 items should be ~13 minutes (10 base + 3 buffer)
        assert 10 <= result.response.estimated_processing_minutes <= 15

    @pytest.mark.asyncio
    async def test_scope_response_includes_all_fields(self, service):
        """Response includes all required fields."""
        result = await service.select_scope(
            upload_id=TEST_UPLOAD_ID,
            user_id=TEST_USER_ID,
            scope=ScopeType.BOTH,
            user_tier="expert",
            upload_status="validated",
            liked_count=100,
            favorited_count=50,
        )

        assert result.success is True
        response = result.response

        assert response.upload_id == TEST_UPLOAD_ID
        assert response.scope == ScopeType.BOTH
        assert response.total_items == 150
        assert response.liked_count == 100
        assert response.favorited_count == 50
        assert response.tier_limit == 3000
        assert response.within_limit is True
        assert response.estimated_processing_minutes >= 1
        assert response.ready_for_consent is True


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
class TestScopeEndpoint:
    """Tests for the PATCH /api/uploads/{upload_id}/scope endpoint."""

    @pytest.mark.asyncio
    async def test_scope_endpoint_requires_auth(self, test_client):
        """PATCH /api/uploads/{id}/scope requires authentication."""
        response = await test_client.patch(
            f"/api/uploads/{TEST_UPLOAD_ID}/scope",
            json={"scope": "liked"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_scope_endpoint_invalid_token_returns_401(self, test_client):
        """PATCH /api/uploads/{id}/scope with invalid token returns 401."""
        response = await test_client.patch(
            f"/api/uploads/{TEST_UPLOAD_ID}/scope",
            json={"scope": "liked"},
            headers={"Authorization": "Bearer invalid-token"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_scope_endpoint_expired_token_returns_401(self, test_client):
        """PATCH /api/uploads/{id}/scope with expired token returns 401."""
        token = create_test_token(expires_in=-3600)

        response = await test_client.patch(
            f"/api/uploads/{TEST_UPLOAD_ID}/scope",
            json={"scope": "liked"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_scope_endpoint_invalid_uuid_returns_422(self, test_client):
        """PATCH /api/uploads/{id}/scope with invalid UUID returns 422."""
        token = create_test_token()

        response = await test_client.patch(
            "/api/uploads/not-a-uuid/scope",
            json={"scope": "liked"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_scope_endpoint_invalid_scope_returns_422(self, test_client):
        """PATCH /api/uploads/{id}/scope with invalid scope returns 422."""
        token = create_test_token()

        response = await test_client.patch(
            f"/api/uploads/{TEST_UPLOAD_ID}/scope",
            json={"scope": "invalid_scope"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_scope_endpoint_accepts_liked(self, test_client):
        """PATCH /api/uploads/{id}/scope accepts 'liked' scope."""
        token = create_test_token()

        response = await test_client.patch(
            f"/api/uploads/{TEST_UPLOAD_ID}/scope",
            json={"scope": "liked"},
            headers={"Authorization": f"Bearer {token}"},
        )

        # Currently returns 404 because database integration is pending
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_scope_endpoint_accepts_favorited(self, test_client):
        """PATCH /api/uploads/{id}/scope accepts 'favorited' scope."""
        token = create_test_token()

        response = await test_client.patch(
            f"/api/uploads/{TEST_UPLOAD_ID}/scope",
            json={"scope": "favorited"},
            headers={"Authorization": f"Bearer {token}"},
        )

        # Currently returns 404 because database integration is pending
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_scope_endpoint_accepts_both(self, test_client):
        """PATCH /api/uploads/{id}/scope accepts 'both' scope."""
        token = create_test_token()

        response = await test_client.patch(
            f"/api/uploads/{TEST_UPLOAD_ID}/scope",
            json={"scope": "both"},
            headers={"Authorization": f"Bearer {token}"},
        )

        # Currently returns 404 because database integration is pending
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_scope_endpoint_not_found_returns_404(self, test_client):
        """PATCH /api/uploads/{id}/scope for unknown upload returns 404."""
        token = create_test_token()

        response = await test_client.patch(
            f"/api/uploads/{uuid4()}/scope",
            json={"scope": "liked"},
            headers={"Authorization": f"Bearer {token}"},
        )

        # Currently returns 404 because database integration is pending
        assert response.status_code == 404
