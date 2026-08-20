"""Immutable provider-neutral moderation values."""

from pydantic import BaseModel, ConfigDict, Field


class _ModerationContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ModerationRequest(_ModerationContract):
    model: str = Field(min_length=1)
    input: list[str] = Field(min_length=1)


class ModerationResult(_ModerationContract):
    flagged: bool
    categories: dict[str, bool]
    category_scores: dict[str, float]


class ModerationResponse(_ModerationContract):
    id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    results: list[ModerationResult] = Field(min_length=1)
