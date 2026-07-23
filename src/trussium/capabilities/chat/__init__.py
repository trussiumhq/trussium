"""Provider-neutral chat-completion capability contracts."""

from trussium.capabilities.chat.models import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ChatRole,
    ChatStreamDeltaEvent,
    ChatStreamEndEvent,
    ChatStreamErrorEvent,
    ChatStreamEvent,
    ChatStreamStartEvent,
    FinishReason,
    TokenUsage,
)

__all__ = [
    "ChatCompletionChoice",
    "ChatCompletionRequest",
    "ChatCompletionResponse",
    "ChatMessage",
    "ChatRole",
    "ChatStreamDeltaEvent",
    "ChatStreamEndEvent",
    "ChatStreamErrorEvent",
    "ChatStreamEvent",
    "ChatStreamStartEvent",
    "FinishReason",
    "TokenUsage",
]
