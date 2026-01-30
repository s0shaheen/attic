"""API routers package."""

from app.routers.uploads import router as uploads_router
from app.routers.user import router as user_router

__all__ = [
    "uploads_router",
    "user_router",
]
