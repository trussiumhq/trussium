"""Immutable provider-neutral batch-job values."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _BatchContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BatchCreateRequest(_BatchContract):
    input_file_id: str = Field(min_length=1)
    endpoint: Literal["/v1/chat/completions"] = "/v1/chat/completions"


class BatchJob(_BatchContract):
    id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    status: str = Field(min_length=1)
    endpoint: str = Field(min_length=1)
    input_file_id: str = Field(min_length=1)
    output_file_id: str | None = None
    error_file_id: str | None = None
