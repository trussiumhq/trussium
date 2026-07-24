"""Server-sent event encoding for chat streams."""

from collections.abc import AsyncIterator

from trussium.capabilities.chat import (
    ChatCapability,
    ChatCompletionRequest,
    ChatStreamEvent,
)


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
    async for event in capability.stream(request):
        yield encode_chat_stream_event(event)
