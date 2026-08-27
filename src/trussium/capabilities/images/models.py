"""Immutable provider-neutral image-generation values."""

from pydantic import BaseModel, ConfigDict, Field

from trussium.capabilities.validation import NonBlankString


class _ImageContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ImageGenerationRequest(_ImageContract):
    model: NonBlankString
    prompt: NonBlankString
    size: str | None = None
    count: int = Field(default=1, ge=1, le=10)


class GeneratedImage(_ImageContract):
    b64_json: str = Field(min_length=1)
    revised_prompt: str | None = None


class ImageGenerationResponse(_ImageContract):
    id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    data: list[GeneratedImage] = Field(min_length=1)
