"""Tests for upload size limits and concurrent upload checks."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.config import Settings, get_settings
from app.core.auth import get_current_user
from app.db.session import get_db
from app.main import app
from app.models.auth import AuthenticatedUser

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TEST_USER_ID = uuid4()
TEST_USER = AuthenticatedUser(id=TEST_USER_ID, email="test@test.com")


def _make_mock_settings() -> MagicMock:
    settings = MagicMock(spec=Settings)
    settings.max_concurrent_uploads = 3
    settings.max_file_size_mb = 500
    settings.supabase_url = "https://test.supabase.co"
    settings.supabase_secret_key = "test-key"
    settings.aws_region = "us-east-1"
    settings.aws_access_key_id = "test"
    settings.aws_secret_access_key = "test"
    settings.sqs_queue_url = None
    return settings


def _make_mock_db(*, active_upload_count: int = 0):
    """Create a mock DB that returns a count for active uploads."""
    mock_db = AsyncMock()

    # For the concurrent upload count query
    count_result = MagicMock()
    count_result.scalar.return_value = active_upload_count
    mock_db.execute = AsyncMock(return_value=count_result)

    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    return mock_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _override_dependencies():
    original = app.dependency_overrides.copy()

    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    app.dependency_overrides[get_db] = lambda: _make_mock_db()
    app.dependency_overrides[get_settings] = _make_mock_settings

    yield

    app.dependency_overrides = original


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestConcurrentUploadLimit:
    async def test_allows_upload_under_limit(self, client):
        """User with < max concurrent uploads can create a new one."""
        mock_db = _make_mock_db(active_upload_count=1)
        app.dependency_overrides[get_db] = lambda: mock_db

        with patch("app.routers.uploads.UploadService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.create_presigned_url = AsyncMock(
                return_value=MagicMock(
                    success=True,
                    upload_id=uuid4(),
                    presigned_url="https://example.com/upload",
                    storage_path="bucket/path.zip",
                    expires_at="2026-01-01T00:00:00Z",
                    max_file_size=524288000,
                )
            )
            mock_svc_cls.return_value = mock_svc

            response = await client.post(
                "/api/uploads/presigned-url",
                json={"filename": "export.zip", "content_type": "application/zip"},
            )

        assert response.status_code == 200

    async def test_blocks_upload_at_limit(self, client):
        """User at max concurrent uploads gets 429."""
        mock_db = _make_mock_db(active_upload_count=3)
        app.dependency_overrides[get_db] = lambda: mock_db

        response = await client.post(
            "/api/uploads/presigned-url",
            json={"filename": "export.zip", "content_type": "application/zip"},
        )

        assert response.status_code == 429
        data = response.json()
        assert "3 uploads in progress" in data["detail"]["detail"]


class TestConfigurableFileSize:
    def test_max_file_size_is_500mb(self):
        """Default max file size is 500MB."""
        from app.services.storage import MAX_FILE_SIZE_BYTES

        assert MAX_FILE_SIZE_BYTES == 500 * 1024 * 1024

    def test_settings_default_concurrent_uploads(self):
        """Default max concurrent uploads is 3."""
        from app.config import Settings

        assert Settings.model_fields["max_concurrent_uploads"].default == 3
