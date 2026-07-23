"""Provider-neutral chat-completion contracts."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _ChatContract(BaseModel):
    """Base configuration shared by chat contracts."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )


class ChatRole(StrEnum):
    """Roles supported by normalized chat messages."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class FinishReason(StrEnum):
    """Normalized reasons for completion termination."""

    STOP = "stop"
    LENGTH = "length"
    TOOL_CALL = "tool_call"
    CONTENT_FILTER = "content_filter"
    ERROR = "error"


class ChatMessage(_ChatContract):
    """A normalized message in a chat conversation."""

    role: ChatRole
    content: str = Field(min_length=1)


class ChatCompletionRequest(_ChatContract):
    """A provider-neutral chat-completion request."""

    model: str = Field(min_length=1)
    messages: list[ChatMessage] = Field(min_length=1)
    temperature: float | None = Field(
        default=None,
        ge=0,
        le=2,
    )
    max_output_tokens: int | None = Field(
        default=None,
        gt=0,
    )
    stream: bool = False


class TokenUsage(_ChatContract):
    """Normalized token usage for a completed request."""

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_total_tokens(self) -> Self:
        """Ensure the reported total matches input and output usage."""
        expected_total = self.input_tokens + self.output_tokens

        if self.total_tokens != expected_total:
            message = "total_tokens must equal input_tokens plus output_tokens"
            raise ValueError(message)

        return self


class ChatCompletionChoice(_ChatContract):
    """One normalized result from a chat completion."""

    index: int = Field(ge=0)
    message: ChatMessage
    finish_reason: FinishReason


class ChatCompletionResponse(_ChatContract):
    """A provider-neutral chat-completion response."""

    id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    choices: list[ChatCompletionChoice] = Field(min_length=1)
    usage: TokenUsage


class ChatStreamStartEvent(_ChatContract):
    """Event emitted when a streamed completion starts."""

    type: Literal["start"] = "start"
    id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)


class ChatStreamDeltaEvent(_ChatContract):
    """Event containing incremental generated content."""

    type: Literal["delta"] = "delta"
    id: str = Field(min_length=1)
    content: str = Field(min_length=1)


class ChatStreamEndEvent(_ChatContract):
    """Event emitted when a streamed completion finishes."""

    type: Literal["end"] = "end"
    id: str = Field(min_length=1)
    finish_reason: FinishReason
    usage: TokenUsage


class ChatStreamErrorEvent(_ChatContract):
    """Event emitted when streamed completion processing fails."""

    type: Literal["error"] = "error"
    id: str | None = Field(default=None, min_length=1)
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)


ChatStreamEvent = Annotated[
    ChatStreamStartEvent | ChatStreamDeltaEvent | ChatStreamEndEvent | ChatStreamErrorEvent,
    Field(discriminator="type"),
]
