"""Tests for chat server-sent event encoding."""

from trussium.api.sse import encode_chat_stream_event
from trussium.capabilities.chat import (
    ChatStreamDeltaEvent,
    ChatStreamErrorEvent,
)


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
