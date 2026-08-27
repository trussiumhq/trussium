"""Immutable provider-neutral reranking values."""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trussium.capabilities.validation import NonBlankString


class _RerankingContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RerankingDocument(_RerankingContract):
    text: NonBlankString


class RerankingRequest(_RerankingContract):
    model: NonBlankString
    query: NonBlankString
    documents: list[RerankingDocument] = Field(min_length=1)
    top_n: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_top_n(self) -> "RerankingRequest":
        if self.top_n is not None and self.top_n > len(self.documents):
            raise ValueError("top_n must not exceed the number of documents")
        return self


class RerankingResult(_RerankingContract):
    index: int = Field(ge=0)
    relevance_score: float


class RerankingResponse(_RerankingContract):
    id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    results: list[RerankingResult] = Field(min_length=1)
