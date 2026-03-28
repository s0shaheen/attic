"""FastAPI application entry point for Attic backend."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_db
from app.models import HealthResponse
from app.routers import chat_router, uploads_router, user_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Application version
VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan event handler."""
    # Startup — validate all prompt files exist before accepting requests
    from app.services.prompt_loader import validate_all_prompts

    validate_all_prompts()
    logger.info({"event": "server_started", "version": VERSION})
    yield
    # Shutdown (if needed)


# Create FastAPI application
app = FastAPI(
    title="Attic API",
    description="Personal analytics platform for TikTok data",
    version=VERSION,
    lifespan=lifespan,
)

# CORS middleware — origins from CORS_ORIGINS env var (comma-separated)
_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(chat_router)
app.include_router(uploads_router)
app.include_router(user_router)


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint.

    Returns:
        HealthResponse with status and version.
    """
    return HealthResponse(status="healthy", version=VERSION)


@app.get("/ready", response_model=HealthResponse)
async def readiness_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """Readiness check — verifies database connectivity.

    Returns:
        HealthResponse with status and version if DB is reachable.
        500 if DB is unreachable.
    """
    await db.execute(text("SELECT 1"))
    return HealthResponse(status="ready", version=VERSION)


@app.get("/api/dev-status")
async def dev_status() -> dict:
    """Dev status endpoint — shows which services are configured.

    Only available in development. Returns service configuration status
    so the dev banner can show what's real vs. fake.
    """
    settings = get_settings()
    if settings.is_production:
        return {"error": "Not available in production"}

    return {
        "environment": settings.environment,
        "services": {
            "apify": "configured" if settings.apify_api_token else "fake",
            "openai": "configured" if settings.openai_api_key else "fake",
            "anthropic": "configured" if settings.anthropic_api_key else "missing",
            "gemini": "configured" if settings.gemini_api_key else "missing",
            "sqs": "configured" if settings.sqs_queue_url else "inline",
            "google_maps": "configured" if settings.google_maps_api_key else "missing",
            "tmdb": "configured" if settings.tmdb_api_key else "missing",
            "spotify": "configured" if settings.spotify_client_id else "missing",
        },
    }
