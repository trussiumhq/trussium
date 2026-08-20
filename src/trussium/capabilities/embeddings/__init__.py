"""Provider-neutral embeddings capability contracts."""

from trussium.capabilities.embeddings.capability import (
    EMBEDDINGS_CAPABILITY_METADATA,
    EMBEDDINGS_CAPABILITY_NAME,
    EmbeddingsCapability,
)
from trussium.capabilities.embeddings.models import (
    EmbeddingInput,
    EmbeddingsRequest,
    EmbeddingsResponse,
    EmbeddingsUsage,
)

__all__ = [
    "EMBEDDINGS_CAPABILITY_METADATA",
    "EMBEDDINGS_CAPABILITY_NAME",
    "EmbeddingInput",
    "EmbeddingsCapability",
    "EmbeddingsRequest",
    "EmbeddingsResponse",
    "EmbeddingsUsage",
]
