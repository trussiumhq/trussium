"""Chat capability provider interface."""

from collections.abc import AsyncIterator
from typing import Final, Protocol, runtime_checkable

from trussium.capabilities.chat.models import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatStreamEvent,
)
from trussium.capabilities.metadata import CapabilityMetadata

CHAT_CAPABILITY_NAME: Final = "chat.completions"
CHAT_CAPABILITY_METADATA: Final = CapabilityMetadata(
    name=CHAT_CAPABILITY_NAME,
    version="v1",
    description="Create normalized provider-neutral chat completions.",
    supports_streaming=True,
)


@runtime_checkable
class ChatCapability(Protocol):
    """Interface implemented by chat-capable provider adapters."""

    async def complete(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        """Execute a non-streaming chat completion.

        Args:
            request: Provider-neutral chat-completion request.

        Returns:
            A normalized chat-completion response.
        """
        ...

    def stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[ChatStreamEvent]:
        """Execute a streaming chat completion.

        Args:
            request: Provider-neutral chat-completion request.

        Returns:
            An asynchronous iterator of normalized streaming events.
        """
        ...


__all__ = ["CHAT_CAPABILITY_METADATA", "CHAT_CAPABILITY_NAME", "ChatCapability"]
