"""SQLAlchemy declarative base for Attic database models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models.

    All models should inherit from this class to be included in
    Alembic migrations and share common configuration.
    """

    pass
