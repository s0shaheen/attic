"""Alembic environment configuration for async SQLAlchemy.

This module configures Alembic to work with asyncpg and SQLAlchemy's
async engine. It imports all models to enable autogenerate support.
"""

import asyncio
from logging.config import fileConfig
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import String, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Load .env so DATABASE_URL is available in CLI context.
# Must run before app.* imports which read env vars via pydantic-settings.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app.db.base import Base  # noqa: E402
from app.db.session import build_database_url  # noqa: E402
from app.models import (  # noqa: E402, F401
    Conversation,
    CostModel,
    MediaEvent,
    Message,
    ProcessingStep,
    PromptTemplate,
    Upload,
    UploadPipelineRun,
    User,
)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the target metadata for autogenerate support
target_metadata = Base.metadata


def get_url() -> str:
    """Get database URL from environment.

    Uses the same logic as the application session factory.
    """
    return build_database_url()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_num_type=String(128),
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """Run migrations with the given connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_num_type=String(128),
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine.

    In this scenario we need to create an async Engine
    and associate a connection with the context.
    """
    configuration = config.get_section(config.config_ini_section, {})
    url = get_url()
    configuration["sqlalchemy.url"] = url

    # Supabase transaction pooler (port 6543) uses PgBouncer —
    # disable prepared statement caching for asyncpg compatibility
    connect_args = {}
    if "pooler.supabase.com" in url or ":6543/" in url:
        connect_args["statement_cache_size"] = 0

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
