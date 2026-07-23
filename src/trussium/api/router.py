"""Top-level API router."""

from fastapi import APIRouter

from trussium.api.chat import router as chat_router
from trussium.api.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(chat_router)
