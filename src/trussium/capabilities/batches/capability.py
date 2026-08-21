"""Batch-inference capability interface."""

from typing import Final, Protocol, runtime_checkable

from trussium.capabilities.batches.models import BatchCreateRequest, BatchJob
from trussium.capabilities.metadata import CapabilityMetadata

BATCHES_CAPABILITY_NAME: Final = "batches"
BATCHES_CAPABILITY_METADATA: Final = CapabilityMetadata(
    name=BATCHES_CAPABILITY_NAME,
    version="v1",
    description="Create, retrieve, and cancel normalized batch inference jobs.",
    supports_streaming=False,
)


@runtime_checkable
class BatchCapability(Protocol):
    async def create(self, request: BatchCreateRequest) -> BatchJob: ...
    async def retrieve(self, batch_id: str) -> BatchJob: ...
    async def cancel(self, batch_id: str) -> BatchJob: ...
