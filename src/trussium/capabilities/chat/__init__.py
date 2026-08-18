"""Provider-neutral chat-completion capability contracts."""

from trussium.capabilities.chat.capability import (
    CHAT_CAPABILITY_METADATA,
    CHAT_CAPABILITY_NAME,
    ChatCapability,
)
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
    "CHAT_CAPABILITY_METADATA",
    "CHAT_CAPABILITY_NAME",
    "ChatCapability",
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
