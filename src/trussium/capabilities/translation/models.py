"""Immutable provider-neutral translation values."""

from pydantic import BaseModel, ConfigDict, Field

from trussium.capabilities.validation import NonBlankString


class _TranslationContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TranslationRequest(_TranslationContract):
    model: NonBlankString
    input: list[NonBlankString] = Field(min_length=1)
    source_language: str | None = Field(default=None, min_length=2, max_length=16)
    target_language: str = Field(min_length=2, max_length=16)
    format: str = Field(default="text", pattern="^(text)$")


class TranslationResult(_TranslationContract):
    text: str = Field(min_length=1)
    source_language: str | None = None
    target_language: str = Field(min_length=2, max_length=16)


class TranslationResponse(_TranslationContract):
    id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    translations: list[TranslationResult] = Field(min_length=1)
