"""OpenAI provider adapter."""

from trussium.providers.openai.chat import (
    OpenAIChatCapability,
    OpenAIProviderError,
)
from trussium.providers.openai.embeddings import OpenAIEmbeddingsCapability
from trussium.providers.openai.health import OpenAICompatibleProviderHealthCheck

__all__ = [
    "OpenAIChatCapability",
    "OpenAICompatibleProviderHealthCheck",
    "OpenAIEmbeddingsCapability",
    "OpenAIProviderError",
]
