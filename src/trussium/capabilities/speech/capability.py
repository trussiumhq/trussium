"""Provider-neutral text-to-speech capability interface."""

from typing import Final, Protocol, runtime_checkable

from trussium.capabilities.metadata import CapabilityMetadata
from trussium.capabilities.speech.models import SpeechRequest, SpeechResponse

SPEECH_CAPABILITY_NAME: Final = "audio.speech"
SPEECH_CAPABILITY_METADATA: Final = CapabilityMetadata(
    name=SPEECH_CAPABILITY_NAME,
    version="v1",
    description="Create normalized provider-neutral speech audio.",
    supports_streaming=False,
)


@runtime_checkable
class SpeechCapability(Protocol):
    async def synthesize(self, request: SpeechRequest) -> SpeechResponse: ...
