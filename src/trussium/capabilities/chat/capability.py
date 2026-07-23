"""Chat capability provider interface."""

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from trussium.capabilities.chat.models import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatStreamEvent,
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
