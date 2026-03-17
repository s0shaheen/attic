"""Pytest fixtures for Attic backend tests."""

import os

# Set environment variables BEFORE importing anything from app
# This is necessary because app.config validates settings at import time
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("SUPABASE_URL", "https://test-project.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "test-secret-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-for-testing-only")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test-aws-key")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test-aws-secret")
os.environ.setdefault("APIFY_API_TOKEN", "test-apify-token")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("STRIPE_SECRET_KEY", "test-stripe-key")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "test-stripe-webhook")
os.environ.setdefault("RESEND_API_KEY", "test-resend-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
os.environ.setdefault("GOOGLE_MAPS_API_KEY", "test-google-maps-key")
os.environ.setdefault("TMDB_API_KEY", "test-tmdb-key")
os.environ.setdefault("SPOTIFY_CLIENT_ID", "test-spotify-id")
os.environ.setdefault("SPOTIFY_CLIENT_SECRET", "test-spotify-secret")

import socket

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def _pg_reachable() -> bool:
    """Check if PostgreSQL is reachable on localhost:5432."""
    try:
        sock = socket.create_connection(("127.0.0.1", 5432), timeout=1)
        sock.close()
        return True
    except OSError:
        return False


_DB_AVAILABLE = _pg_reachable()


def pytest_collection_modifyitems(config, items):
    """Auto-skip tests marked with @pytest.mark.requires_db when no DB is available."""
    if _DB_AVAILABLE:
        return
    skip_marker = pytest.mark.skip(reason="PostgreSQL not available on localhost:5432")
    for item in items:
        if "requires_db" in item.keywords:
            item.add_marker(skip_marker)


@pytest.fixture
async def client() -> AsyncClient:
    """Create an async test client for the FastAPI application.

    Yields:
        AsyncClient configured to test the FastAPI app.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
