"""API routers package."""

from app.routers.chat import router as chat_router
from app.routers.uploads import router as uploads_router
from app.routers.user import router as user_router

__all__ = [
    "chat_router",
    "uploads_router",
    "user_router",
]
