"""Async SQLAlchemy session factory for Supabase PostgreSQL.

Provides database connection management with support for both local
Supabase CLI development and cloud Supabase deployment.
"""

import logging
import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)


def build_database_url() -> str:
    """Construct the async DATABASE_URL from environment variables.

    Priority:
    1. DATABASE_URL if set directly
    2. USE_LOCAL_SUPABASE=true uses local Supabase CLI defaults
    3. Build from SUPABASE_URL + SUPABASE_DB_PASSWORD

    Returns:
        A postgresql+asyncpg:// connection string.

    Raises:
        ValueError: If required environment variables are missing.
    """
    # Direct override for flexibility
    direct_url = os.getenv("DATABASE_URL")
    if direct_url:
        # Normalize to asyncpg driver
        if direct_url.startswith("postgresql://"):
            direct_url = direct_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return direct_url

    # Local development with Supabase CLI
    if os.getenv("USE_LOCAL_SUPABASE", "").lower() in ("1", "true", "yes"):
        host = os.getenv("SUPABASE_LOCAL_HOST", "127.0.0.1")
        port = os.getenv("SUPABASE_LOCAL_PORT", "54322")
        return f"postgresql+asyncpg://postgres:postgres@{host}:{port}/postgres"

    # Build from Supabase cloud credentials
    supabase_url = os.getenv("SUPABASE_URL")
    db_password = os.getenv("SUPABASE_DB_PASSWORD")

    if not supabase_url:
        raise ValueError(
            "DATABASE_URL, SUPABASE_URL, or USE_LOCAL_SUPABASE must be set. "
            "See docs/setup/supabase.md for configuration."
        )

    # Extract project reference from SUPABASE_URL
    # Format: https://{project_ref}.supabase.co
    project_ref = supabase_url.replace("https://", "").replace(".supabase.co", "").strip("/")

    if not db_password:
        raise ValueError(
            "SUPABASE_DB_PASSWORD must be set for cloud database connections. "
            "Find it in Supabase Dashboard > Project Settings > Database > Connection string."
        )

    return f"postgresql+asyncpg://postgres.{project_ref}:{db_password}@aws-0-us-east-1.pooler.supabase.com:6543/postgres"


def _get_pool_settings() -> dict:
    """Return connection pool configuration from environment."""
    return {
        "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
        "pool_pre_ping": True,
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "300")),
    }


# Module-level engine and session factory (lazy initialization)
_engine = None
_session_factory = None


def _initialize() -> None:
    """Initialize the module-level engine and session factory."""
    global _engine, _session_factory
    if _engine is None:
        url = build_database_url()
        pool_settings = _get_pool_settings()

        _engine = create_async_engine(
            url,
            echo=os.getenv("DB_ECHO", "").lower() in ("1", "true", "yes"),
            **pool_settings,
        )
        _session_factory = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        logger.info(
            "Database engine created",
            extra={"pool_size": pool_settings["pool_size"]},
        )


def get_engine():
    """Return the async engine, initializing if needed."""
    _initialize()
    return _engine


def async_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the async session factory, initializing if needed."""
    _initialize()
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
