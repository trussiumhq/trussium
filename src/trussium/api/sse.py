"""Server-sent event encoding for chat streams."""

from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse
from starlette.types import Receive, Scope, Send

from trussium.capabilities.chat import (
    ChatCapability,
    ChatCompletionRequest,
    ChatStreamEvent,
)
from trussium.runtime.streaming import close_async_resource


class ClosableStreamingResponse(StreamingResponse):
    """Streaming response that promptly finalizes its body iterator."""

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        """Send the response and close its iterator during every exit path."""
        try:
            await super().__call__(scope, receive, send)
        finally:
            await close_async_resource(self.body_iterator)


def encode_chat_stream_event(event: ChatStreamEvent) -> str:
    """Encode a normalized chat event as a server-sent event.

    Args:
        event: Normalized chat streaming event.

    Returns:
        An SSE-formatted event containing the serialized event.
    """
    return f"event: {event.type}\ndata: {event.model_dump_json()}\n\n"


async def stream_chat_events(
    capability: ChatCapability,
    request: ChatCompletionRequest,
) -> AsyncIterator[str]:
    """Stream normalized chat events encoded as SSE messages.

    Args:
        capability: Configured provider-neutral chat capability.
        request: Normalized streaming chat request.

    Yields:
        SSE-formatted normalized chat events.
    """
    events = capability.stream(request)

    try:
        async for event in events:
            yield encode_chat_stream_event(event)
    finally:
        await close_async_resource(events)
