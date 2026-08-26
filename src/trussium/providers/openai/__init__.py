"""OpenAI provider adapter."""

from trussium.providers.openai.batches import OpenAIBatchCapability
from trussium.providers.openai.chat import (
    OpenAIChatCapability,
    OpenAIProviderError,
)
from trussium.providers.openai.embeddings import OpenAIEmbeddingsCapability
from trussium.providers.openai.health import OpenAICompatibleProviderHealthCheck
from trussium.providers.openai.images import OpenAIImageGenerationCapability
from trussium.providers.openai.moderation import OpenAIModerationCapability
from trussium.providers.openai.speech import OpenAISpeechCapability
from trussium.providers.openai.transcription import OpenAITranscriptionCapability
from trussium.providers.openai.videos import OpenAIVideoCapability

__all__ = [
    "OpenAIBatchCapability",
    "OpenAIChatCapability",
    "OpenAICompatibleProviderHealthCheck",
    "OpenAIEmbeddingsCapability",
    "OpenAIImageGenerationCapability",
    "OpenAIModerationCapability",
    "OpenAIProviderError",
    "OpenAISpeechCapability",
    "OpenAITranscriptionCapability",
    "OpenAIVideoCapability",
]
