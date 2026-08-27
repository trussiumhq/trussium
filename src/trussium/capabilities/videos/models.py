"""Immutable provider-neutral video job values."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from trussium.capabilities.validation import NonBlankString


class _VideoContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class VideoCreateRequest(_VideoContract):
    model: NonBlankString
    prompt: NonBlankString
    seconds: Literal["4", "8", "12"] | None = None
    size: Literal["720x1280", "1280x720", "1024x1792", "1792x1024"] | None = None


class VideoJob(_VideoContract):
    id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    status: str = Field(min_length=1)
    progress: int = Field(ge=0, le=100)
    seconds: str | None = None
    size: str | None = None
