"""Moderation capability provider interface."""

from typing import Final, Protocol, runtime_checkable

from trussium.capabilities.metadata import CapabilityMetadata
from trussium.capabilities.moderation.models import ModerationRequest, ModerationResponse

MODERATION_CAPABILITY_NAME: Final = "moderation"
MODERATION_CAPABILITY_METADATA: Final = CapabilityMetadata(
    name=MODERATION_CAPABILITY_NAME,
    version="v1",
    description="Classify text with normalized provider-neutral moderation.",
    supports_streaming=False,
)


@runtime_checkable
class ModerationCapability(Protocol):
    async def moderate(self, request: ModerationRequest) -> ModerationResponse: ...
