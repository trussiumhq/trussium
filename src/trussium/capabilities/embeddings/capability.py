"""Embeddings capability provider interface."""

from typing import Final, Protocol, runtime_checkable

from trussium.capabilities.embeddings.models import EmbeddingsRequest, EmbeddingsResponse
from trussium.capabilities.metadata import CapabilityMetadata

EMBEDDINGS_CAPABILITY_NAME: Final = "embeddings"
EMBEDDINGS_CAPABILITY_METADATA: Final = CapabilityMetadata(
    name=EMBEDDINGS_CAPABILITY_NAME,
    version="v1",
    description="Create normalized provider-neutral text embeddings.",
    supports_streaming=False,
)


@runtime_checkable
class EmbeddingsCapability(Protocol):
    """Interface implemented by embeddings-capable provider adapters."""

    async def embed(self, request: EmbeddingsRequest) -> EmbeddingsResponse:
        """Create provider-neutral embeddings for the supplied inputs."""
        ...
