"""Immutable provider-neutral audio-transcription values."""

from pydantic import BaseModel, ConfigDict, Field


class _TranscriptionContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AudioInput(_TranscriptionContract):
    """Ephemeral audio payload supplied by the HTTP boundary."""

    filename: str = Field(min_length=1)
    content_type: str | None = None
    data: bytes = Field(min_length=1)


class TranscriptionRequest(_TranscriptionContract):
    model: str = Field(min_length=1)
    audio: AudioInput
    language: str | None = Field(default=None, min_length=1)
    prompt: str | None = Field(default=None, min_length=1)
    temperature: float | None = Field(default=None, ge=0, le=1)


class TranscriptionSegment(_TranscriptionContract):
    id: int = Field(ge=0)
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    text: str = Field(min_length=1)


class TranscriptionResponse(_TranscriptionContract):
    id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    text: str = Field(min_length=1)
    language: str | None = None
    duration: float | None = Field(default=None, ge=0)
    segments: list[TranscriptionSegment] = Field(default_factory=list)
