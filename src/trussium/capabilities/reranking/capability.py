"""Reranking capability interface."""

from typing import Final, Protocol, runtime_checkable

from trussium.capabilities.metadata import CapabilityMetadata
from trussium.capabilities.reranking.models import RerankingRequest, RerankingResponse

RERANKING_CAPABILITY_NAME: Final = "rerankings"
RERANKING_CAPABILITY_METADATA: Final = CapabilityMetadata(
    name=RERANKING_CAPABILITY_NAME,
    version="v1",
    description="Rank candidate texts against a query.",
    supports_streaming=False,
)


@runtime_checkable
class RerankingCapability(Protocol):
    async def rerank(self, request: RerankingRequest) -> RerankingResponse: ...
