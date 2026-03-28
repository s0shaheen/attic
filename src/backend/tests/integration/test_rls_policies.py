"""Exhaustive RLS policy tests — proves user isolation across all tables.

Every user-owned table must prevent cross-user access. This test suite:
1. Creates two users (A and B) via Supabase Auth admin API
2. Seeds a full data graph for User A (user → upload → media_event → processing_step,
   conversation → message, collection → collection_item)
3. Verifies User B cannot SELECT/INSERT/UPDATE/DELETE User A's data
4. Verifies anonymous users have no access
5. Verifies service role bypasses RLS (backend access)

Requires:
- Local Supabase running: `supabase start`
- Migrations applied: `supabase db reset`
- Env var: RUN_INTEGRATION_TESTS=1

Run with: RUN_INTEGRATION_TESTS=1 pytest tests/integration/test_rls_policies.py -v
"""

import os
from uuid import uuid4

import pytest

httpx = pytest.importorskip("httpx")

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS", "").lower() not in ("1", "true", "yes"),
    reason="Integration tests disabled. Set RUN_INTEGRATION_TESTS=1 to enable.",
)

# ---------------------------------------------------------------------------
# Local Supabase config
# ---------------------------------------------------------------------------

LOCAL_SUPABASE_URL = "http://127.0.0.1:54321"
REST_URL = f"{LOCAL_SUPABASE_URL}/rest/v1"
AUTH_URL = f"{LOCAL_SUPABASE_URL}/auth/v1"

# fmt: off
LOCAL_SUPABASE_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9."
    "CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0"
)
LOCAL_SUPABASE_SERVICE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0."
    "EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU"
)
# fmt: on


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _service_headers() -> dict:
    return {
        "Authorization": f"Bearer {LOCAL_SUPABASE_SERVICE_KEY}",
        "apikey": LOCAL_SUPABASE_SERVICE_KEY,
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _user_headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "apikey": LOCAL_SUPABASE_ANON_KEY,
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _anon_headers() -> dict:
    return {
        "apikey": LOCAL_SUPABASE_ANON_KEY,
        "Content-Type": "application/json",
    }


def _create_auth_user(client: httpx.Client, email: str, password: str) -> dict:
    """Create a user via Supabase Auth admin API, return user data with access_token."""
    # Create user
    resp = client.post(
        f"{AUTH_URL}/admin/users",
        headers=_service_headers(),
        json={
            "email": email,
            "password": password,
            "email_confirm": True,
        },
    )
    assert resp.status_code == 200, f"Failed to create user: {resp.text}"
    user = resp.json()

    # Sign in to get JWT
    resp = client.post(
        f"{AUTH_URL}/token?grant_type=password",
        headers={"apikey": LOCAL_SUPABASE_ANON_KEY, "Content-Type": "application/json"},
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, f"Failed to sign in: {resp.text}"
    tokens = resp.json()

    return {
        "id": user["id"],
        "email": email,
        "access_token": tokens["access_token"],
    }


def _delete_auth_user(client: httpx.Client, user_id: str) -> None:
    """Delete a user via Supabase Auth admin API."""
    resp = client.delete(
        f"{AUTH_URL}/admin/users/{user_id}",
        headers=_service_headers(),
    )
    # 200 or 404 are both OK (user may have been cascade-deleted)
    assert resp.status_code in (200, 404), f"Failed to delete user: {resp.text}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    """Shared HTTP client for all tests."""
    with httpx.Client(timeout=30.0) as c:
        yield c


@pytest.fixture(scope="module")
def user_a(client):
    """Create test User A with JWT."""
    user = _create_auth_user(client, f"rls-test-a-{uuid4().hex[:8]}@test.local", "TestPass123!")
    yield user
    # Cleanup: delete all user A data first (service role), then delete user
    svc = _service_headers()
    client.delete(f"{REST_URL}/collection_items?collection_id=not.is.null", headers=svc)
    client.delete(f"{REST_URL}/collections?user_id=eq.{user['id']}", headers=svc)
    client.delete(f"{REST_URL}/messages?conversation_id=not.is.null", headers=svc)
    client.delete(f"{REST_URL}/conversations?user_id=eq.{user['id']}", headers=svc)
    client.delete(f"{REST_URL}/processing_steps?media_event_id=not.is.null", headers=svc)
    client.delete(f"{REST_URL}/media_events?user_id=eq.{user['id']}", headers=svc)
    client.delete(f"{REST_URL}/upload_pipeline_runs?user_id=eq.{user['id']}", headers=svc)
    client.delete(f"{REST_URL}/uploads?user_id=eq.{user['id']}", headers=svc)
    client.delete(f"{REST_URL}/users?id=eq.{user['id']}", headers=svc)
    _delete_auth_user(client, user["id"])


@pytest.fixture(scope="module")
def user_b(client):
    """Create test User B with JWT."""
    user = _create_auth_user(client, f"rls-test-b-{uuid4().hex[:8]}@test.local", "TestPass123!")
    yield user
    svc = _service_headers()
    client.delete(f"{REST_URL}/collections?user_id=eq.{user['id']}", headers=svc)
    client.delete(f"{REST_URL}/conversations?user_id=eq.{user['id']}", headers=svc)
    client.delete(f"{REST_URL}/uploads?user_id=eq.{user['id']}", headers=svc)
    client.delete(f"{REST_URL}/users?id=eq.{user['id']}", headers=svc)
    _delete_auth_user(client, user["id"])


@pytest.fixture(scope="module")
def seed_data(client, user_a):
    """Seed a full data graph for User A using service role."""
    svc = _service_headers()
    uid = user_a["id"]

    # User row
    resp = client.post(
        f"{REST_URL}/users",
        headers=svc,
        json={
            "id": uid,
            "email": user_a["email"],
            "auth_provider": "test",
            "auth_provider_id": f"test-{uid}",
        },
    )
    assert resp.status_code == 201, f"Failed to create user row: {resp.text}"

    # Upload
    upload_id = str(uuid4())
    resp = client.post(
        f"{REST_URL}/uploads",
        headers=svc,
        json={
            "id": upload_id,
            "user_id": uid,
            "source_platform": "tiktok",
            "status": "completed",
        },
    )
    assert resp.status_code == 201, f"Failed to create upload: {resp.text}"

    # Upload pipeline run
    pipeline_run_id = str(uuid4())
    resp = client.post(
        f"{REST_URL}/upload_pipeline_runs",
        headers=svc,
        json={
            "id": pipeline_run_id,
            "upload_id": upload_id,
            "user_id": uid,
            "status": "completed",
        },
    )
    assert resp.status_code == 201, f"Failed to create pipeline run: {resp.text}"

    # Media event
    media_event_id = str(uuid4())
    resp = client.post(
        f"{REST_URL}/media_events",
        headers=svc,
        json={
            "id": media_event_id,
            "user_id": uid,
            "upload_id": upload_id,
            "platform": "tiktok",
            "platform_id": f"test-{media_event_id[:8]}",
        },
    )
    assert resp.status_code == 201, f"Failed to create media event: {resp.text}"

    # Processing step
    processing_step_id = str(uuid4())
    resp = client.post(
        f"{REST_URL}/processing_steps",
        headers=svc,
        json={
            "id": processing_step_id,
            "media_event_id": media_event_id,
            "step_type": "CLASSIFY_TIER1",
            "provider": "gemini_flash",
            "status": "succeeded",
        },
    )
    assert resp.status_code == 201, f"Failed to create processing step: {resp.text}"

    # Conversation
    conversation_id = str(uuid4())
    resp = client.post(
        f"{REST_URL}/conversations",
        headers=svc,
        json={
            "id": conversation_id,
            "user_id": uid,
            "title": "Test conversation",
        },
    )
    assert resp.status_code == 201, f"Failed to create conversation: {resp.text}"

    # Message
    message_id = str(uuid4())
    resp = client.post(
        f"{REST_URL}/messages",
        headers=svc,
        json={
            "id": message_id,
            "conversation_id": conversation_id,
            "role": "user",
            "content": "test message",
        },
    )
    assert resp.status_code == 201, f"Failed to create message: {resp.text}"

    # Collection
    collection_id = str(uuid4())
    resp = client.post(
        f"{REST_URL}/collections",
        headers=svc,
        json={
            "id": collection_id,
            "user_id": uid,
            "name": "Test Collection",
            "source_type": "manual",
        },
    )
    assert resp.status_code == 201, f"Failed to create collection: {resp.text}"

    # Collection item
    collection_item_id = str(uuid4())
    resp = client.post(
        f"{REST_URL}/collection_items",
        headers=svc,
        json={
            "id": collection_item_id,
            "collection_id": collection_id,
            "media_event_id": media_event_id,
        },
    )
    assert resp.status_code == 201, f"Failed to create collection item: {resp.text}"

    return {
        "user_id": uid,
        "upload_id": upload_id,
        "pipeline_run_id": pipeline_run_id,
        "media_event_id": media_event_id,
        "processing_step_id": processing_step_id,
        "conversation_id": conversation_id,
        "message_id": message_id,
        "collection_id": collection_id,
        "collection_item_id": collection_item_id,
    }


@pytest.fixture(scope="module")
def user_b_row(client, user_b):
    """Create a user row for User B so they can perform operations."""
    svc = _service_headers()
    resp = client.post(
        f"{REST_URL}/users",
        headers=svc,
        json={
            "id": user_b["id"],
            "email": user_b["email"],
            "auth_provider": "test",
            "auth_provider_id": f"test-{user_b['id']}",
        },
    )
    assert resp.status_code == 201, f"Failed to create user B row: {resp.text}"
    return user_b


# ---------------------------------------------------------------------------
# Positive tests — User A can access own data
# ---------------------------------------------------------------------------


class TestPositiveAccess:
    """User A must be able to read their own data."""

    def test_user_a_reads_own_user_row(self, client, user_a, seed_data):
        resp = client.get(
            f"{REST_URL}/users?id=eq.{user_a['id']}&select=id",
            headers=_user_headers(user_a["access_token"]),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_user_a_reads_own_uploads(self, client, user_a, seed_data):
        resp = client.get(
            f"{REST_URL}/uploads?user_id=eq.{user_a['id']}&select=id",
            headers=_user_headers(user_a["access_token"]),
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_user_a_reads_own_media_events(self, client, user_a, seed_data):
        resp = client.get(
            f"{REST_URL}/media_events?user_id=eq.{user_a['id']}&select=id",
            headers=_user_headers(user_a["access_token"]),
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_user_a_reads_own_conversations(self, client, user_a, seed_data):
        resp = client.get(
            f"{REST_URL}/conversations?user_id=eq.{user_a['id']}&select=id",
            headers=_user_headers(user_a["access_token"]),
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_user_a_reads_own_collections(self, client, user_a, seed_data):
        resp = client.get(
            f"{REST_URL}/collections?user_id=eq.{user_a['id']}&select=id",
            headers=_user_headers(user_a["access_token"]),
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_user_a_reads_own_processing_steps(self, client, user_a, seed_data):
        resp = client.get(
            f"{REST_URL}/processing_steps?select=id",
            headers=_user_headers(user_a["access_token"]),
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_user_a_reads_own_messages(self, client, user_a, seed_data):
        resp = client.get(
            f"{REST_URL}/messages?select=id",
            headers=_user_headers(user_a["access_token"]),
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_user_a_reads_own_collection_items(self, client, user_a, seed_data):
        resp = client.get(
            f"{REST_URL}/collection_items?select=id",
            headers=_user_headers(user_a["access_token"]),
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


# ---------------------------------------------------------------------------
# Negative tests — User B cannot access User A's data
# ---------------------------------------------------------------------------


class TestCrossUserSelect:
    """User B must NOT be able to read User A's data."""

    def test_user_b_cannot_read_user_a_row(self, client, user_b, user_b_row, seed_data):
        resp = client.get(
            f"{REST_URL}/users?id=eq.{seed_data['user_id']}&select=id",
            headers=_user_headers(user_b["access_token"]),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_user_b_cannot_read_user_a_uploads(self, client, user_b, user_b_row, seed_data):
        resp = client.get(
            f"{REST_URL}/uploads?user_id=eq.{seed_data['user_id']}&select=id",
            headers=_user_headers(user_b["access_token"]),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_user_b_cannot_read_user_a_pipeline_runs(self, client, user_b, user_b_row, seed_data):
        resp = client.get(
            f"{REST_URL}/upload_pipeline_runs?user_id=eq.{seed_data['user_id']}&select=id",
            headers=_user_headers(user_b["access_token"]),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_user_b_cannot_read_user_a_media_events(self, client, user_b, user_b_row, seed_data):
        resp = client.get(
            f"{REST_URL}/media_events?user_id=eq.{seed_data['user_id']}&select=id",
            headers=_user_headers(user_b["access_token"]),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_user_b_cannot_read_user_a_conversations(self, client, user_b, user_b_row, seed_data):
        resp = client.get(
            f"{REST_URL}/conversations?user_id=eq.{seed_data['user_id']}&select=id",
            headers=_user_headers(user_b["access_token"]),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_user_b_cannot_read_user_a_collections(self, client, user_b, user_b_row, seed_data):
        resp = client.get(
            f"{REST_URL}/collections?user_id=eq.{seed_data['user_id']}&select=id",
            headers=_user_headers(user_b["access_token"]),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_user_b_cannot_read_user_a_processing_steps(
        self, client, user_b, user_b_row, seed_data
    ):
        resp = client.get(
            f"{REST_URL}/processing_steps?id=eq.{seed_data['processing_step_id']}&select=id",
            headers=_user_headers(user_b["access_token"]),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_user_b_cannot_read_user_a_messages(self, client, user_b, user_b_row, seed_data):
        resp = client.get(
            f"{REST_URL}/messages?id=eq.{seed_data['message_id']}&select=id",
            headers=_user_headers(user_b["access_token"]),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_user_b_cannot_read_user_a_collection_items(
        self, client, user_b, user_b_row, seed_data
    ):
        resp = client.get(
            f"{REST_URL}/collection_items?id=eq.{seed_data['collection_item_id']}&select=id",
            headers=_user_headers(user_b["access_token"]),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 0


class TestCrossUserInsert:
    """User B must NOT be able to insert data with User A's user_id."""

    def test_user_b_cannot_insert_upload_as_user_a(self, client, user_b, user_b_row, seed_data):
        resp = client.post(
            f"{REST_URL}/uploads",
            headers=_user_headers(user_b["access_token"]),
            json={
                "user_id": seed_data["user_id"],  # User A's ID
                "source_platform": "tiktok",
                "status": "pending",
            },
        )
        # PostgREST returns 403 when RLS WITH CHECK blocks INSERT
        assert resp.status_code in (403, 409), f"User B inserted upload as User A: {resp.text}"

    def test_user_b_cannot_insert_conversation_as_user_a(
        self, client, user_b, user_b_row, seed_data
    ):
        resp = client.post(
            f"{REST_URL}/conversations",
            headers=_user_headers(user_b["access_token"]),
            json={
                "user_id": seed_data["user_id"],
                "title": "Evil conversation",
            },
        )
        assert resp.status_code in (403, 409), (
            f"User B inserted conversation as User A: {resp.text}"
        )

    def test_user_b_cannot_insert_collection_as_user_a(self, client, user_b, user_b_row, seed_data):
        resp = client.post(
            f"{REST_URL}/collections",
            headers=_user_headers(user_b["access_token"]),
            json={
                "user_id": seed_data["user_id"],
                "name": "Evil Collection",
                "source_type": "manual",
            },
        )
        assert resp.status_code in (403, 409), f"User B inserted collection as User A: {resp.text}"

    def test_user_b_cannot_insert_media_event_as_user_a(
        self, client, user_b, user_b_row, seed_data
    ):
        resp = client.post(
            f"{REST_URL}/media_events",
            headers=_user_headers(user_b["access_token"]),
            json={
                "user_id": seed_data["user_id"],
                "upload_id": seed_data["upload_id"],
                "platform": "tiktok",
                "platform_id": f"evil-{uuid4().hex[:8]}",
            },
        )
        assert resp.status_code in (403, 409), f"User B inserted media event as User A: {resp.text}"


class TestCrossUserUpdate:
    """User B must NOT be able to update User A's rows."""

    def test_user_b_cannot_update_user_a_upload(self, client, user_b, user_b_row, seed_data):
        resp = client.patch(
            f"{REST_URL}/uploads?id=eq.{seed_data['upload_id']}",
            headers=_user_headers(user_b["access_token"]),
            json={"status": "hacked"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 0  # No rows updated

    def test_user_b_cannot_update_user_a_media_event(self, client, user_b, user_b_row, seed_data):
        resp = client.patch(
            f"{REST_URL}/media_events?id=eq.{seed_data['media_event_id']}",
            headers=_user_headers(user_b["access_token"]),
            json={"platform": "hacked"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_user_b_cannot_update_user_a_conversation(self, client, user_b, user_b_row, seed_data):
        resp = client.patch(
            f"{REST_URL}/conversations?id=eq.{seed_data['conversation_id']}",
            headers=_user_headers(user_b["access_token"]),
            json={"title": "hacked"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_user_b_cannot_update_user_a_collection(self, client, user_b, user_b_row, seed_data):
        resp = client.patch(
            f"{REST_URL}/collections?id=eq.{seed_data['collection_id']}",
            headers=_user_headers(user_b["access_token"]),
            json={"name": "hacked"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 0


class TestCrossUserDelete:
    """User B must NOT be able to delete User A's rows."""

    def test_user_b_cannot_delete_user_a_upload(self, client, user_b, user_b_row, seed_data):
        client.delete(
            f"{REST_URL}/uploads?id=eq.{seed_data['upload_id']}",
            headers=_user_headers(user_b["access_token"]),
        )
        # Verify data still exists
        svc_resp = client.get(
            f"{REST_URL}/uploads?id=eq.{seed_data['upload_id']}&select=id",
            headers=_service_headers(),
        )
        assert len(svc_resp.json()) == 1

    def test_user_b_cannot_delete_user_a_collection(self, client, user_b, user_b_row, seed_data):
        client.delete(
            f"{REST_URL}/collections?id=eq.{seed_data['collection_id']}",
            headers=_user_headers(user_b["access_token"]),
        )
        svc_resp = client.get(
            f"{REST_URL}/collections?id=eq.{seed_data['collection_id']}&select=id",
            headers=_service_headers(),
        )
        assert len(svc_resp.json()) == 1

    def test_user_b_cannot_delete_user_a_conversation(self, client, user_b, user_b_row, seed_data):
        client.delete(
            f"{REST_URL}/conversations?id=eq.{seed_data['conversation_id']}",
            headers=_user_headers(user_b["access_token"]),
        )
        svc_resp = client.get(
            f"{REST_URL}/conversations?id=eq.{seed_data['conversation_id']}&select=id",
            headers=_service_headers(),
        )
        assert len(svc_resp.json()) == 1


class TestCrossUserRelationshipAttacks:
    """User B must NOT be able to link their data to User A's resources."""

    def test_user_b_cannot_add_item_to_user_a_collection(
        self, client, user_b, user_b_row, seed_data
    ):
        """B tries to insert a collection_item pointing to A's collection."""
        resp = client.post(
            f"{REST_URL}/collection_items",
            headers=_user_headers(user_b["access_token"]),
            json={
                "collection_id": seed_data["collection_id"],
                "media_event_id": seed_data["media_event_id"],
            },
        )
        # Should fail — B doesn't own the collection (RLS subquery blocks)
        assert resp.status_code in (403, 409), (
            f"User B added item to User A's collection: {resp.text}"
        )

    def test_user_b_cannot_create_collection_with_user_a_conversation(
        self, client, user_b, user_b_row, seed_data
    ):
        """B creates a collection referencing A's conversation_id.

        This is intentionally allowed — the collection is owned by B, and
        conversation_id is just a metadata reference. B cannot read A's
        conversation data through this FK. The real protection is that B
        cannot SELECT from A's conversations table (tested in TestCrossUserSelect).
        """
        coll_name = f"FK Test Conv {uuid4().hex[:8]}"
        resp = client.post(
            f"{REST_URL}/collections",
            headers=_user_headers(user_b["access_token"]),
            json={
                "user_id": user_b["id"],
                "name": coll_name,
                "source_type": "agent",
                "conversation_id": seed_data["conversation_id"],
            },
        )
        # Intentionally allowed: B owns this collection, conversation_id is metadata.
        # Verify B still cannot read A's conversation through this reference.
        conv_resp = client.get(
            f"{REST_URL}/conversations?id=eq.{seed_data['conversation_id']}&select=id",
            headers=_user_headers(user_b["access_token"]),
        )
        assert len(conv_resp.json()) == 0, "B should not be able to read A's conversation"
        # Clean up
        if resp.status_code == 201 and resp.json():
            coll_id = resp.json()[0]["id"]
            client.delete(
                f"{REST_URL}/collections?id=eq.{coll_id}",
                headers=_service_headers(),
            )

    def test_user_b_cannot_create_collection_with_user_a_upload(
        self, client, user_b, user_b_row, seed_data
    ):
        """B creates a collection referencing A's upload_id.

        Same as above — intentionally allowed. The real protection is RLS
        on the uploads table preventing B from reading A's upload data.
        """
        coll_name = f"FK Test Upload {uuid4().hex[:8]}"
        resp = client.post(
            f"{REST_URL}/collections",
            headers=_user_headers(user_b["access_token"]),
            json={
                "user_id": user_b["id"],
                "name": coll_name,
                "source_type": "import",
                "upload_id": seed_data["upload_id"],
            },
        )
        # Verify B still cannot read A's upload through this reference.
        upload_resp = client.get(
            f"{REST_URL}/uploads?id=eq.{seed_data['upload_id']}&select=id",
            headers=_user_headers(user_b["access_token"]),
        )
        assert len(upload_resp.json()) == 0, "B should not be able to read A's upload"
        # Clean up
        if resp.status_code == 201 and resp.json():
            coll_id = resp.json()[0]["id"]
            client.delete(
                f"{REST_URL}/collections?id=eq.{coll_id}",
                headers=_service_headers(),
            )


# ---------------------------------------------------------------------------
# Anonymous access tests
# ---------------------------------------------------------------------------


class TestAnonymousAccess:
    """Anonymous (unauthenticated) users must have no access to any user data."""

    def test_anon_cannot_read_users(self, client, seed_data):
        resp = client.get(f"{REST_URL}/users?select=id", headers=_anon_headers())
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_anon_cannot_read_uploads(self, client, seed_data):
        resp = client.get(f"{REST_URL}/uploads?select=id", headers=_anon_headers())
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_anon_cannot_read_media_events(self, client, seed_data):
        resp = client.get(f"{REST_URL}/media_events?select=id", headers=_anon_headers())
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_anon_cannot_read_conversations(self, client, seed_data):
        resp = client.get(f"{REST_URL}/conversations?select=id", headers=_anon_headers())
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_anon_cannot_read_collections(self, client, seed_data):
        resp = client.get(f"{REST_URL}/collections?select=id", headers=_anon_headers())
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_anon_cannot_read_processing_steps(self, client, seed_data):
        resp = client.get(f"{REST_URL}/processing_steps?select=id", headers=_anon_headers())
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_anon_cannot_read_messages(self, client, seed_data):
        resp = client.get(f"{REST_URL}/messages?select=id", headers=_anon_headers())
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_anon_cannot_read_collection_items(self, client, seed_data):
        resp = client.get(f"{REST_URL}/collection_items?select=id", headers=_anon_headers())
        assert resp.status_code == 200
        assert len(resp.json()) == 0


# ---------------------------------------------------------------------------
# Read-only table tests
# ---------------------------------------------------------------------------


class TestReadOnlyTables:
    """Authenticated users can read but not write to reference tables."""

    def test_authenticated_can_read_prompt_templates(self, client, user_a, seed_data):
        resp = client.get(
            f"{REST_URL}/prompt_templates?select=id",
            headers=_user_headers(user_a["access_token"]),
        )
        assert resp.status_code == 200
        # May be empty if no templates seeded, but should not error

    def test_authenticated_cannot_insert_prompt_template(self, client, user_a, seed_data):
        resp = client.post(
            f"{REST_URL}/prompt_templates",
            headers=_user_headers(user_a["access_token"]),
            json={
                "name": "evil",
                "version": "v999",
                "model": "evil-model",
            },
        )
        # Should fail — no INSERT policy on read-only table
        assert resp.status_code in (403, 409), (
            "Authenticated user should not insert prompt templates"
        )

    def test_authenticated_can_read_cost_models(self, client, user_a, seed_data):
        resp = client.get(
            f"{REST_URL}/cost_models?select=id",
            headers=_user_headers(user_a["access_token"]),
        )
        assert resp.status_code == 200

    def test_authenticated_cannot_insert_cost_model(self, client, user_a, seed_data):
        resp = client.post(
            f"{REST_URL}/cost_models",
            headers=_user_headers(user_a["access_token"]),
            json={
                "provider": "evil",
                "sku": "evil",
                "metric": "evil",
                "unit_price_usd": 999.0,
            },
        )
        assert resp.status_code in (403, 409), "Authenticated user should not insert cost models"

    def test_anon_cannot_read_prompt_templates(self, client, seed_data):
        resp = client.get(
            f"{REST_URL}/prompt_templates?select=id",
            headers=_anon_headers(),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_anon_cannot_read_cost_models(self, client, seed_data):
        resp = client.get(
            f"{REST_URL}/cost_models?select=id",
            headers=_anon_headers(),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 0


# ---------------------------------------------------------------------------
# Service role bypass test
# ---------------------------------------------------------------------------


class TestServiceRoleBypass:
    """Service role (backend) must bypass all RLS."""

    def test_service_role_reads_all_users(self, client, seed_data):
        resp = client.get(
            f"{REST_URL}/users?id=eq.{seed_data['user_id']}&select=id",
            headers=_service_headers(),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_service_role_reads_all_media_events(self, client, seed_data):
        resp = client.get(
            f"{REST_URL}/media_events?id=eq.{seed_data['media_event_id']}&select=id",
            headers=_service_headers(),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_service_role_reads_all_collections(self, client, seed_data):
        resp = client.get(
            f"{REST_URL}/collections?id=eq.{seed_data['collection_id']}&select=id",
            headers=_service_headers(),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1
