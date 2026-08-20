"""Audio-transcription capability provider interface."""

from typing import Final, Protocol, runtime_checkable

from trussium.capabilities.metadata import CapabilityMetadata
from trussium.capabilities.transcription.models import TranscriptionRequest, TranscriptionResponse

TRANSCRIPTION_CAPABILITY_NAME: Final = "audio.transcriptions"
TRANSCRIPTION_CAPABILITY_METADATA: Final = CapabilityMetadata(
    name=TRANSCRIPTION_CAPABILITY_NAME,
    version="v1",
    description="Create normalized provider-neutral audio transcriptions.",
    supports_streaming=False,
)


@runtime_checkable
class TranscriptionCapability(Protocol):
    async def transcribe(self, request: TranscriptionRequest) -> TranscriptionResponse: ...
