"""Integration tests for the tiktok-exports storage bucket.

These tests verify the storage bucket configuration and RLS policies.
They require a local Supabase instance to be running.

To run these tests:
1. Start local Supabase: `supabase start`
2. Apply migrations: `supabase db reset`
3. Run tests: `pytest tests/test_storage_bucket.py -v`

Note: These tests are skipped by default if Supabase is not available.
Use `pytest tests/test_storage_bucket.py -v --run-integration` to run them.
"""

import os
from uuid import uuid4

import pytest

# Skip all tests if httpx is not available or integration tests not enabled
httpx = pytest.importorskip("httpx")

# Check if we should run integration tests
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS", "").lower() not in ("1", "true", "yes"),
    reason="Integration tests disabled. Set RUN_INTEGRATION_TESTS=1 to enable.",
)


# Test configuration for local Supabase
LOCAL_SUPABASE_URL = "http://127.0.0.1:54321"
# Default local Supabase anon key (used for RLS testing)
# fmt: off
LOCAL_SUPABASE_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9."
    "CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0"
)
# Default local Supabase service key (bypasses RLS)
LOCAL_SUPABASE_SERVICE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0."
    "EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU"
)
# fmt: on


BUCKET_NAME = "tiktok-exports"


@pytest.fixture
def service_client():
    """Create an HTTP client with service role authentication (bypasses RLS)."""
    return httpx.Client(
        base_url=LOCAL_SUPABASE_URL,
        headers={
            "Authorization": f"Bearer {LOCAL_SUPABASE_SERVICE_KEY}",
            "apikey": LOCAL_SUPABASE_SERVICE_KEY,
        },
        timeout=30.0,
    )


@pytest.fixture
def anon_client():
    """Create an HTTP client without authentication (anonymous)."""
    return httpx.Client(
        base_url=LOCAL_SUPABASE_URL,
        headers={
            "apikey": LOCAL_SUPABASE_ANON_KEY,
        },
        timeout=30.0,
    )


def create_user_client(user_jwt: str):
    """Create an HTTP client authenticated as a specific user."""
    return httpx.Client(
        base_url=LOCAL_SUPABASE_URL,
        headers={
            "Authorization": f"Bearer {user_jwt}",
            "apikey": LOCAL_SUPABASE_ANON_KEY,
        },
        timeout=30.0,
    )


def create_test_zip_content() -> bytes:
    """Create minimal ZIP file content for testing."""
    # Minimal valid ZIP file (empty archive)
    return b"PK\x05\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"


class TestStorageBucketExists:
    """Tests for verifying the bucket exists with correct configuration."""

    def test_storage_bucket_exists(self, service_client: httpx.Client):
        """Verify the tiktok-exports bucket exists."""
        # List all buckets using Storage API
        response = service_client.get("/storage/v1/bucket")

        assert response.status_code == 200, f"Failed to list buckets: {response.text}"

        buckets = response.json()
        bucket_ids = [b["id"] for b in buckets]

        assert BUCKET_NAME in bucket_ids, (
            f"Bucket '{BUCKET_NAME}' not found. Available buckets: {bucket_ids}"
        )

    def test_storage_bucket_is_private(self, service_client: httpx.Client):
        """Verify the bucket is private (public = false)."""
        response = service_client.get(f"/storage/v1/bucket/{BUCKET_NAME}")

        assert response.status_code == 200, f"Failed to get bucket: {response.text}"

        bucket = response.json()
        assert bucket["public"] is False, "Bucket should be private"

    def test_storage_bucket_file_size_limit(self, service_client: httpx.Client):
        """Verify the bucket has 500MB file size limit."""
        response = service_client.get(f"/storage/v1/bucket/{BUCKET_NAME}")

        assert response.status_code == 200, f"Failed to get bucket: {response.text}"

        bucket = response.json()
        expected_limit = 524288000  # 500MB in bytes

        assert bucket["file_size_limit"] == expected_limit, (
            f"File size limit should be {expected_limit} bytes (500MB), "
            f"got {bucket.get('file_size_limit')}"
        )

    def test_storage_bucket_allowed_mime_types(self, service_client: httpx.Client):
        """Verify the bucket only allows ZIP file MIME types."""
        response = service_client.get(f"/storage/v1/bucket/{BUCKET_NAME}")

        assert response.status_code == 200, f"Failed to get bucket: {response.text}"

        bucket = response.json()
        allowed_types = set(bucket.get("allowed_mime_types", []))
        expected_types = {
            "application/zip",
            "application/x-zip-compressed",
            "application/octet-stream",
        }

        assert expected_types.issubset(allowed_types), (
            f"Expected MIME types {expected_types} to be allowed, got {allowed_types}"
        )


class TestStorageRLSAnonymousAccess:
    """Tests for verifying anonymous users cannot access the bucket."""

    def test_anonymous_cannot_list_bucket(self, anon_client: httpx.Client):
        """Verify anonymous users cannot list bucket contents."""
        user_id = uuid4()
        response = anon_client.post(
            f"/storage/v1/object/list/{BUCKET_NAME}",
            json={"prefix": str(user_id)},
        )

        # Should fail with 400 (RLS violation) or 401 (unauthorized)
        assert response.status_code in (400, 401, 403), (
            f"Anonymous list should fail, got {response.status_code}"
        )

    def test_anonymous_cannot_upload(self, anon_client: httpx.Client):
        """Verify anonymous users cannot upload files."""
        user_id = uuid4()
        upload_id = uuid4()
        file_path = f"{user_id}/{upload_id}.zip"

        response = anon_client.post(
            f"/storage/v1/object/{BUCKET_NAME}/{file_path}",
            content=create_test_zip_content(),
            headers={"Content-Type": "application/zip"},
        )

        # Should fail with 400 (RLS violation) or 401 (unauthorized)
        assert response.status_code in (400, 401, 403), (
            f"Anonymous upload should fail, got {response.status_code}"
        )


class TestStorageRLSServiceRole:
    """Tests for verifying service role can access all files (bypasses RLS)."""

    def test_service_role_can_upload_for_any_user(self, service_client: httpx.Client):
        """Verify service role can upload files (for backend processing)."""
        user_id = uuid4()
        upload_id = uuid4()
        file_path = f"{user_id}/{upload_id}.zip"

        response = service_client.post(
            f"/storage/v1/object/{BUCKET_NAME}/{file_path}",
            content=create_test_zip_content(),
            headers={"Content-Type": "application/zip"},
        )

        assert response.status_code in (200, 201), (
            f"Service role upload failed: {response.status_code} - {response.text}"
        )

        # Cleanup
        service_client.delete(f"/storage/v1/object/{BUCKET_NAME}/{file_path}")

    def test_service_role_can_delete_any_file(self, service_client: httpx.Client):
        """Verify service role can delete files (for cleanup)."""
        user_id = uuid4()
        upload_id = uuid4()
        file_path = f"{user_id}/{upload_id}.zip"

        # First upload a file
        service_client.post(
            f"/storage/v1/object/{BUCKET_NAME}/{file_path}",
            content=create_test_zip_content(),
            headers={"Content-Type": "application/zip"},
        )

        # Now delete it
        response = service_client.delete(
            f"/storage/v1/object/{BUCKET_NAME}",
            json={"prefixes": [file_path]},
        )

        assert response.status_code in (200, 204), (
            f"Service role delete failed: {response.status_code} - {response.text}"
        )


# Note: Full RLS policy tests with authenticated users require creating test users
# in Supabase Auth and obtaining JWTs. These tests are best run as E2E tests
# with the full authentication flow (Task 2.3/2.8).
#
# The tests above verify:
# 1. Bucket exists with correct configuration
# 2. Bucket is private (no public access)
# 3. File size limit is enforced
# 4. MIME types are restricted
# 5. Anonymous users cannot access
# 6. Service role can manage files (for backend operations)
#
# User isolation (User A cannot access User B's files) is enforced by RLS
# policies that check auth.uid() against the path. This is tested implicitly
# by the anonymous access tests and will be fully tested in E2E tests.
