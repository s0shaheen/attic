"""Configuration re-export for core module.

This module re-exports the application settings from app.config
to provide a consistent import path within the core module.

Note: We don't import `settings` here to avoid triggering
Settings initialization at module load time (which requires env vars).
Use `get_settings()` as a dependency instead.
"""

from app.config import Settings, get_settings

__all__ = [
    "Settings",
    "get_settings",
]
