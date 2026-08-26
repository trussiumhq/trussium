"""Top-level API router."""

from fastapi import APIRouter

from trussium.api.batches import router as batches_router
from trussium.api.capabilities import router as capabilities_router
from trussium.api.chat import router as chat_router
from trussium.api.embeddings import router as embeddings_router
from trussium.api.health import router as health_router
from trussium.api.images import router as images_router
from trussium.api.moderation import router as moderation_router
from trussium.api.providers import router as providers_router
from trussium.api.reranking import router as reranking_router
from trussium.api.speech import router as speech_router
from trussium.api.tools import router as tools_router
from trussium.api.transcription import router as transcription_router
from trussium.api.translation import router as translation_router
from trussium.api.videos import router as videos_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(batches_router)
api_router.include_router(capabilities_router)
api_router.include_router(chat_router)
api_router.include_router(embeddings_router)
api_router.include_router(moderation_router)
api_router.include_router(providers_router)
api_router.include_router(reranking_router)
api_router.include_router(speech_router)
api_router.include_router(images_router)
api_router.include_router(transcription_router)
api_router.include_router(translation_router)
api_router.include_router(tools_router)
api_router.include_router(videos_router)
