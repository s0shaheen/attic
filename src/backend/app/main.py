"""FastAPI application entry point for Attic backend."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.models import HealthResponse

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
    # Startup
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


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint.

    Returns:
        HealthResponse with status and version.
    """
    return HealthResponse(status="healthy", version=VERSION)
