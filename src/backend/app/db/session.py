"""Async SQLAlchemy session factory for Supabase PostgreSQL.

Provides database connection management with support for both local
Supabase CLI development and cloud Supabase deployment.

The engine is initialized lazily on first use via get_settings() — no
os.getenv calls at module level, so .env loading is handled entirely
by pydantic-settings.
"""

import logging
import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)


def _normalize_database_url(url: str) -> str:
    """Ensure the URL uses the asyncpg driver."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def build_database_url() -> str:
    """Construct the async DATABASE_URL from environment variables.

    Used ONLY by alembic/env.py (CLI context without FastAPI DI).
    Application code uses get_db() which reads from Settings.

    Priority:
    1. DATABASE_URL if set directly
    2. USE_LOCAL_SUPABASE=true uses local Supabase CLI defaults
    3. Build from SUPABASE_URL + SUPABASE_DB_PASSWORD

    Returns:
        A postgresql+asyncpg:// connection string.

    Raises:
        ValueError: If required environment variables are missing.
    """
    direct_url = os.getenv("DATABASE_URL")
    if direct_url:
        return _normalize_database_url(direct_url)

    if os.getenv("USE_LOCAL_SUPABASE", "").lower() in ("1", "true", "yes"):
        host = os.getenv("SUPABASE_LOCAL_HOST", "127.0.0.1")
        port = os.getenv("SUPABASE_LOCAL_PORT", "54322")
        return f"postgresql+asyncpg://postgres:postgres@{host}:{port}/postgres"

    supabase_url = os.getenv("SUPABASE_URL")
    db_password = os.getenv("SUPABASE_DB_PASSWORD")

    if not supabase_url:
        raise ValueError(
            "DATABASE_URL, SUPABASE_URL, or USE_LOCAL_SUPABASE must be set. "
            "See docs/setup/supabase.md for configuration."
        )

    project_ref = supabase_url.replace("https://", "").replace(".supabase.co", "").strip("/")

    if not db_password:
        raise ValueError(
            "SUPABASE_DB_PASSWORD must be set for cloud database connections. "
            "Find it in Supabase Dashboard > Project Settings > Database > Connection string."
        )

    return f"postgresql+asyncpg://postgres.{project_ref}:{db_password}@aws-0-us-east-1.pooler.supabase.com:6543/postgres"


# Module-level engine and session factory (lazy initialization)
_engine = None
_session_factory = None


def _initialize_from_settings() -> None:
    """Initialize the engine from pydantic Settings (reads .env via pydantic-settings)."""
    global _engine, _session_factory
    if _engine is None:
        from app.config import get_settings

        settings = get_settings()
        url = _normalize_database_url(settings.database_url)

        _engine = create_async_engine(
            url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=300,
        )
        _session_factory = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        logger.info("Database engine created")


def get_engine():
    """Return the async engine, initializing if needed."""
    _initialize_from_settings()
    return _engine


def async_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the async session factory, initializing if needed."""
    _initialize_from_settings()
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session.

    Usage:
        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()

    The session is automatically committed on success or rolled back on error.
    """
    factory = async_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
