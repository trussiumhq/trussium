"""Provider-neutral audio-transcription capability contracts."""

from trussium.capabilities.transcription.capability import (
    TRANSCRIPTION_CAPABILITY_METADATA,
    TRANSCRIPTION_CAPABILITY_NAME,
    TranscriptionCapability,
)
from trussium.capabilities.transcription.models import (
    AudioInput,
    TranscriptionRequest,
    TranscriptionResponse,
    TranscriptionSegment,
)

__all__ = [
    "TRANSCRIPTION_CAPABILITY_METADATA",
    "TRANSCRIPTION_CAPABILITY_NAME",
    "AudioInput",
    "TranscriptionCapability",
    "TranscriptionRequest",
    "TranscriptionResponse",
    "TranscriptionSegment",
]
