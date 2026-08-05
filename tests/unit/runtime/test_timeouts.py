"""Tests for provider-neutral execution timeout enforcement."""

import asyncio
from collections.abc import AsyncIterator

import pytest

from trussium.capabilities.chat import (
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
from trussium.capabilities.errors import (
    CapabilityErrorCategory,
    CapabilityExecutionError,
)
from trussium.runtime import (
    PROVIDER_REQUEST_TIMEOUT_CODE,
    PROVIDER_REQUEST_TIMEOUT_MESSAGE,
    PROVIDER_STREAM_TIMEOUT_CODE,
    PROVIDER_STREAM_TIMEOUT_MESSAGE,
    TimeoutChatCapability,
)


def create_request(*, streaming: bool = False) -> ChatCompletionRequest:
    """Create a normalized chat request."""
    return ChatCompletionRequest(
        model="test-model",
        messages=[
            ChatMessage(
                role=ChatRole.USER,
                content="Hello.",
            )
        ],
        stream=streaming,
    )


def create_response(request: ChatCompletionRequest) -> ChatCompletionResponse:
    """Create a normalized chat response."""
    return ChatCompletionResponse(
        id="timeout-response-123",
        provider="test-provider",
        model=request.model,
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatMessage(
                    role=ChatRole.ASSISTANT,
                    content="Hello.",
                ),
                finish_reason=FinishReason.STOP,
            )
        ],
        usage=TokenUsage(
            input_tokens=1,
            output_tokens=1,
            total_tokens=2,
        ),
    )


class DelayedChatProvider:
    """Delay provider responses and record iterator finalization."""

    def __init__(
        self,
        *,
        complete_delay: float = 0,
        stream_delays: tuple[float, ...] = (),
    ) -> None:
        """Initialize deterministic delays."""
        self.complete_delay = complete_delay
        self.stream_delays = stream_delays
        self.complete_finalized = False
        self.stream_finalized = False

    async def complete(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        """Return a response after the configured delay."""
        try:
            await asyncio.sleep(self.complete_delay)
            return create_response(request)
        finally:
            self.complete_finalized = True

    async def stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[ChatStreamEvent]:
        """Emit a complete stream after the configured inter-event delays."""
        response_id = "timeout-stream-123"

        try:
            for index, delay in enumerate(self.stream_delays):
                await asyncio.sleep(delay)

                if index == 0:
                    yield ChatStreamStartEvent(
                        id=response_id,
                        provider="test-provider",
                        model=request.model,
                    )
                else:
                    yield ChatStreamDeltaEvent(
                        id=response_id,
                        content=f"chunk-{index}",
                    )

            yield ChatStreamEndEvent(
                id=response_id,
                finish_reason=FinishReason.STOP,
                usage=TokenUsage(
                    input_tokens=1,
                    output_tokens=1,
                    total_tokens=2,
                ),
            )
        finally:
            self.stream_finalized = True


async def collect_events(
    events: AsyncIterator[ChatStreamEvent],
) -> list[ChatStreamEvent]:
    """Collect a normalized provider stream."""
    return [event async for event in events]


@pytest.mark.parametrize(
    ("request_timeout", "stream_timeout", "message"),
    [
        (0, 1, "Provider request timeout must be positive"),
        (-1, 1, "Provider request timeout must be positive"),
        (1, 0, "Stream idle timeout must be positive"),
        (1, -1, "Stream idle timeout must be positive"),
    ],
)
def test_timeout_decorator_rejects_non_positive_values(
    request_timeout: float,
    stream_timeout: float,
    message: str,
) -> None:
    """Runtime timeout values should always be positive."""
    with pytest.raises(ValueError, match=message):
        TimeoutChatCapability(
            DelayedChatProvider(),
            provider_request_seconds=request_timeout,
            stream_idle_seconds=stream_timeout,
        )


def test_complete_returns_before_deadline() -> None:
    """A provider response within its deadline should pass through unchanged."""
    provider = DelayedChatProvider()
    capability = TimeoutChatCapability(
        provider,
        provider_request_seconds=1,
        stream_idle_seconds=1,
    )

    response = asyncio.run(capability.complete(create_request()))

    assert response == create_response(create_request())
    assert provider.complete_finalized is True


def test_complete_timeout_is_normalized_and_finalizes_provider() -> None:
    """A runtime request deadline should become an upstream timeout error."""
    provider = DelayedChatProvider(complete_delay=1)
    capability = TimeoutChatCapability(
        provider,
        provider_request_seconds=0.001,
        stream_idle_seconds=1,
    )

    with pytest.raises(CapabilityExecutionError) as error_info:
        asyncio.run(capability.complete(create_request()))

    error = error_info.value
    assert error.code == PROVIDER_REQUEST_TIMEOUT_CODE
    assert error.message == PROVIDER_REQUEST_TIMEOUT_MESSAGE
    assert error.category is CapabilityErrorCategory.UPSTREAM_TIMEOUT
    assert provider.complete_finalized is True


def test_active_stream_can_exceed_idle_timeout_in_total() -> None:
    """Each provider event should reset the stream idle deadline."""
    provider = DelayedChatProvider(stream_delays=(0.01, 0.01, 0.01))
    capability = TimeoutChatCapability(
        provider,
        provider_request_seconds=1,
        stream_idle_seconds=0.02,
    )

    events = asyncio.run(
        collect_events(
            capability.stream(create_request(streaming=True)),
        )
    )

    assert [event.type for event in events] == ["start", "delta", "delta", "end"]
    assert provider.stream_finalized is True


def test_initial_stream_timeout_is_normalized_and_finalizes_provider() -> None:
    """A timeout while opening a stream should emit one error without an ID."""
    provider = DelayedChatProvider(stream_delays=(1,))
    capability = TimeoutChatCapability(
        provider,
        provider_request_seconds=1,
        stream_idle_seconds=0.001,
    )

    events = asyncio.run(
        collect_events(
            capability.stream(create_request(streaming=True)),
        )
    )

    assert len(events) == 1
    event = events[0]
    assert event.type == "error"
    assert event.id is None
    assert event.code == PROVIDER_STREAM_TIMEOUT_CODE
    assert event.message == PROVIDER_STREAM_TIMEOUT_MESSAGE
    assert provider.stream_finalized is True


def test_mid_stream_timeout_preserves_response_id_and_finalizes_provider() -> None:
    """A stalled active stream should emit one correlated error event."""
    provider = DelayedChatProvider(stream_delays=(0, 1))
    capability = TimeoutChatCapability(
        provider,
        provider_request_seconds=1,
        stream_idle_seconds=0.001,
    )

    events = asyncio.run(
        collect_events(
            capability.stream(create_request(streaming=True)),
        )
    )

    assert [event.type for event in events] == ["start", "error"]
    error = events[-1]
    assert error.id == "timeout-stream-123"
    assert provider.stream_finalized is True


def test_caller_cancellation_is_not_converted_to_timeout() -> None:
    """External cancellation should retain its cooperative cancellation meaning."""
    provider = DelayedChatProvider(complete_delay=1)
    capability = TimeoutChatCapability(
        provider,
        provider_request_seconds=10,
        stream_idle_seconds=10,
    )

    async def cancel_execution() -> None:
        task = asyncio.create_task(capability.complete(create_request()))
        await asyncio.sleep(0)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel_execution())

    assert provider.complete_finalized is True
