"""Database package for Attic backend.

Exports the declarative base, async session factory, and FastAPI dependency.
"""

from app.db.base import Base
from app.db.session import async_session_factory, get_db

__all__ = ["Base", "async_session_factory", "get_db"]
