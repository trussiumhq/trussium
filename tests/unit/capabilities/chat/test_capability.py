"""Tests for the chat capability provider interface."""

import asyncio
from collections.abc import AsyncIterator

from trussium.capabilities.chat import (
    ChatCapability,
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ChatRole,
    ChatStreamDeltaEvent,
    ChatStreamEndEvent,
    ChatStreamEvent,
    ChatStreamStartEvent,
    FinishReason,
    TokenUsage,
)


class StubChatCapability:
    """Structural test implementation of the chat capability."""

    async def complete(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        """Return a deterministic normalized completion."""
        return ChatCompletionResponse(
            id="chat-stub-1",
            provider="stub",
            model=request.model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(
                        role=ChatRole.ASSISTANT,
                        content="Stub response.",
                    ),
                    finish_reason=FinishReason.STOP,
                )
            ],
            usage=TokenUsage(
                input_tokens=2,
                output_tokens=2,
                total_tokens=4,
            ),
        )

    async def stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[ChatStreamEvent]:
        """Yield deterministic normalized streaming events."""
        response_id = "chat-stub-stream-1"

        yield ChatStreamStartEvent(
            id=response_id,
            provider="stub",
            model=request.model,
        )

        yield ChatStreamDeltaEvent(
            id=response_id,
            content="Stub ",
        )

        yield ChatStreamDeltaEvent(
            id=response_id,
            content="response.",
        )

        yield ChatStreamEndEvent(
            id=response_id,
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(
                input_tokens=2,
                output_tokens=2,
                total_tokens=4,
            ),
        )


def create_request(*, stream: bool = False) -> ChatCompletionRequest:
    """Create a normalized request for capability tests."""
    return ChatCompletionRequest(
        model="stub-model",
        messages=[
            ChatMessage(
                role=ChatRole.USER,
                content="Hello.",
            )
        ],
        stream=stream,
    )


async def execute_completion(
    capability: ChatCapability,
    request: ChatCompletionRequest,
) -> ChatCompletionResponse:
    """Consume a completion through the capability interface."""
    return await capability.complete(request)


async def collect_stream(
    capability: ChatCapability,
    request: ChatCompletionRequest,
) -> list[ChatStreamEvent]:
    """Collect streaming events through the capability interface."""
    return [event async for event in capability.stream(request)]


def test_structural_implementation_satisfies_protocol() -> None:
    """An implementation should not need explicit inheritance."""
    capability = StubChatCapability()

    assert isinstance(capability, ChatCapability)


def test_completion_can_be_consumed_through_protocol() -> None:
    """The interface should expose normalized completion behavior."""
    capability: ChatCapability = StubChatCapability()
    request = create_request()

    response = asyncio.run(
        execute_completion(
            capability,
            request,
        )
    )

    assert response.provider == "stub"
    assert response.model == "stub-model"
    assert response.choices[0].message.content == "Stub response."
    assert response.choices[0].finish_reason is FinishReason.STOP


def test_stream_can_be_consumed_through_protocol() -> None:
    """The interface should expose normalized streaming events."""
    capability: ChatCapability = StubChatCapability()
    request = create_request(stream=True)

    events = asyncio.run(
        collect_stream(
            capability,
            request,
        )
    )

    assert len(events) == 4

    assert isinstance(events[0], ChatStreamStartEvent)
    assert events[0].provider == "stub"

    assert isinstance(events[1], ChatStreamDeltaEvent)
    assert events[1].content == "Stub "

    assert isinstance(events[2], ChatStreamDeltaEvent)
    assert events[2].content == "response."

    assert isinstance(events[3], ChatStreamEndEvent)
    assert events[3].finish_reason is FinishReason.STOP
    assert events[3].usage.total_tokens == 4
