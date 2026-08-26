"""Provider-neutral translation capability interface."""

from typing import Final, Protocol, runtime_checkable

from trussium.capabilities.metadata import CapabilityMetadata
from trussium.capabilities.translation.models import TranslationRequest, TranslationResponse

TRANSLATION_CAPABILITY_NAME: Final = "translations"
TRANSLATION_CAPABILITY_METADATA: Final = CapabilityMetadata(
    name=TRANSLATION_CAPABILITY_NAME,
    version="v1",
    description="Create normalized provider-neutral text translations.",
    supports_streaming=False,
)


@runtime_checkable
class TranslationCapability(Protocol):
    async def translate(self, request: TranslationRequest) -> TranslationResponse: ...
