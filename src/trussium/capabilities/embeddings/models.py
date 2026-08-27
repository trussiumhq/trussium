"""Immutable provider-neutral embeddings values."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trussium.capabilities.validation import NonBlankString


class _EmbeddingsContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EmbeddingInput(_EmbeddingsContract):
    """One input and its normalized vector."""

    index: int = Field(ge=0)
    embedding: list[float] = Field(min_length=1)


class EmbeddingsUsage(_EmbeddingsContract):
    """Provider-neutral embedding token usage."""

    input_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_total_tokens(self) -> Self:
        if self.total_tokens != self.input_tokens:
            raise ValueError("total_tokens must equal input_tokens for embeddings")
        return self


class EmbeddingsRequest(_EmbeddingsContract):
    """A provider-neutral embeddings request."""

    model: NonBlankString
    input: list[NonBlankString] = Field(min_length=1)


class EmbeddingsResponse(_EmbeddingsContract):
    """A provider-neutral embeddings response."""

    id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    data: list[EmbeddingInput] = Field(min_length=1)
    usage: EmbeddingsUsage
