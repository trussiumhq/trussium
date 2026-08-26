"""Provider-neutral text-to-speech contracts."""

from trussium.capabilities.speech.capability import (
    SPEECH_CAPABILITY_METADATA,
    SPEECH_CAPABILITY_NAME,
    SpeechCapability,
)
from trussium.capabilities.speech.models import SpeechRequest, SpeechResponse

__all__ = [
    "SPEECH_CAPABILITY_METADATA",
    "SPEECH_CAPABILITY_NAME",
    "SpeechCapability",
    "SpeechRequest",
    "SpeechResponse",
]
