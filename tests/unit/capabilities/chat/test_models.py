"""Tests for normalized chat-completion contracts."""

import pytest
from pydantic import TypeAdapter, ValidationError

from trussium.capabilities.chat import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ChatRole,
    ChatStreamDeltaEvent,
    ChatStreamEvent,
    FinishReason,
    TokenUsage,
)


def test_chat_completion_request_accepts_valid_input() -> None:
    """A minimal valid chat request should be accepted."""
    request = ChatCompletionRequest(
        model="trussium-default",
        messages=[
            ChatMessage(
                role=ChatRole.USER,
                content="Hello, Trussium.",
            )
        ],
    )

    assert request.model == "trussium-default"
    assert request.messages[0].role is ChatRole.USER
    assert request.stream is False
    assert request.temperature is None
    assert request.max_output_tokens is None


def test_chat_completion_request_requires_messages() -> None:
    """A request without messages should be rejected."""
    with pytest.raises(ValidationError):
        ChatCompletionRequest(
            model="trussium-default",
            messages=[],
        )


def test_chat_completion_request_rejects_invalid_temperature() -> None:
    """Temperature values outside the supported range should fail."""
    with pytest.raises(ValidationError):
        ChatCompletionRequest(
            model="trussium-default",
            messages=[
                ChatMessage(
                    role=ChatRole.USER,
                    content="Hello.",
                )
            ],
            temperature=2.1,
        )


def test_chat_contracts_reject_unknown_fields() -> None:
    """Unknown fields should not silently enter normalized contracts."""
    with pytest.raises(ValidationError):
        ChatMessage.model_validate(
            {
                "role": "user",
                "content": "Hello.",
                "unexpected": True,
            }
        )


def test_chat_contracts_are_immutable() -> None:
    """Validated contracts should not be mutated during execution."""
    message = ChatMessage(
        role=ChatRole.USER,
        content="Original content.",
    )

    with pytest.raises(ValidationError):
        message.content = "Changed content."


def test_token_usage_accepts_consistent_total() -> None:
    """Token totals should match input and output usage."""
    usage = TokenUsage(
        input_tokens=4,
        output_tokens=6,
        total_tokens=10,
    )

    assert usage.total_tokens == 10


def test_token_usage_rejects_inconsistent_total() -> None:
    """Inconsistent token totals should be rejected."""
    with pytest.raises(
        ValidationError,
        match="total_tokens must equal",
    ):
        TokenUsage(
            input_tokens=4,
            output_tokens=6,
            total_tokens=9,
        )


def test_chat_completion_response_serializes_normalized_data() -> None:
    """A normalized response should serialize predictably."""
    response = ChatCompletionResponse(
        id="chat-123",
        provider="example-provider",
        model="example-model",
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatMessage(
                    role=ChatRole.ASSISTANT,
                    content="Hello from Trussium.",
                ),
                finish_reason=FinishReason.STOP,
            )
        ],
        usage=TokenUsage(
            input_tokens=5,
            output_tokens=4,
            total_tokens=9,
        ),
    )

    serialized = response.model_dump(mode="json")

    assert serialized["id"] == "chat-123"
    assert serialized["provider"] == "example-provider"
    assert serialized["choices"][0]["finish_reason"] == "stop"
    assert serialized["usage"]["total_tokens"] == 9


def test_stream_event_uses_type_discriminator() -> None:
    """The stream-event union should resolve the correct event model."""
    adapter: TypeAdapter[ChatStreamEvent] = TypeAdapter(ChatStreamEvent)

    event = adapter.validate_python(
        {
            "type": "delta",
            "id": "chat-123",
            "content": "Hello",
        }
    )

    assert isinstance(event, ChatStreamDeltaEvent)
    assert event.content == "Hello"


def test_stream_event_rejects_unknown_event_type() -> None:
    """Unsupported streaming event types should be rejected."""
    adapter: TypeAdapter[ChatStreamEvent] = TypeAdapter(ChatStreamEvent)

    with pytest.raises(ValidationError):
        adapter.validate_python(
            {
                "type": "unknown",
                "id": "chat-123",
            }
        )
