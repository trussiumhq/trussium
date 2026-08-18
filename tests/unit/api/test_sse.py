"""Tests for chat server-sent event encoding."""

import asyncio
from collections.abc import AsyncIterator
from typing import cast

from trussium.api.sse import encode_chat_stream_event, stream_chat_events
from trussium.capabilities.chat import (
    ChatCapability,
    ChatCompletionRequest,
    ChatMessage,
    ChatRole,
    ChatStreamDeltaEvent,
    ChatStreamErrorEvent,
    ChatStreamEvent,
)


class DirectStreamingCapability:
    """Provide one event through the compatibility streaming helper."""

    async def stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[ChatStreamEvent]:
        """Yield one normalized event."""
        _ = request
        yield ChatStreamDeltaEvent(id="chat-direct", content="Hello")


def test_encode_delta_event_as_sse() -> None:
    """A delta event should include its event name and JSON payload."""
    event = ChatStreamDeltaEvent(
        id="chat-123",
        content="Hello",
    )

    encoded = encode_chat_stream_event(event)

    assert encoded == ('event: delta\ndata: {"type":"delta","id":"chat-123","content":"Hello"}\n\n')


def test_encode_error_event_as_sse() -> None:
    """An error event should preserve its normalized error payload."""
    event = ChatStreamErrorEvent(
        id="chat-123",
        code="provider_failed",
        message="The provider failed.",
    )

    encoded = encode_chat_stream_event(event)

    assert encoded == (
        "event: error\n"
        "data: "
        '{"type":"error","id":"chat-123",'
        '"code":"provider_failed",'
        '"message":"The provider failed."}\n'
        "\n"
    )


def test_direct_capability_streaming_helper_remains_compatible() -> None:
    """Existing direct callers should retain capability-to-SSE behavior."""
    request = ChatCompletionRequest(
        model="test-model",
        messages=[ChatMessage(role=ChatRole.USER, content="Hello")],
        stream=True,
    )

    async def collect() -> list[str]:
        return [
            event
            async for event in stream_chat_events(
                cast(ChatCapability, DirectStreamingCapability()),
                request,
            )
        ]

    assert asyncio.run(collect()) == [
        'event: delta\ndata: {"type":"delta","id":"chat-direct","content":"Hello"}\n\n'
    ]
