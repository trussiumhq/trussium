"""Immutable provider-neutral text-to-speech values."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from trussium.capabilities.validation import NonBlankString


class _SpeechContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SpeechRequest(_SpeechContract):
    model: NonBlankString
    input: NonBlankString
    voice: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
    response_format: Literal["mp3", "opus", "aac", "flac", "wav", "pcm"] = "mp3"
    speed: float = Field(default=1.0, ge=0.25, le=4.0)


class SpeechResponse(_SpeechContract):
    id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    audio: str = Field(min_length=1)
    response_format: str = Field(min_length=1)
