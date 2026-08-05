"""Tests for structured provider execution logging."""

import asyncio
import logging
from asyncio import CancelledError
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Self, cast

import pytest

from trussium.capabilities.chat import (
    ChatCapability,
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
from trussium.capabilities.errors import (
    CapabilityErrorCategory,
    CapabilityExecutionError,
)
from trussium.observability import (
    CHAT_CAPABILITY_NAME,
    UNEXPECTED_PROVIDER_ERROR_CODE,
    LoggingChatCapability,
    LoggingProviderChatCapability,
    RuntimeContextFilter,
)
from trussium.runtime import (
    PROVIDER_REQUEST_TIMEOUT_CODE,
    PROVIDER_STREAM_TIMEOUT_CODE,
    ExecutionContext,
    TimeoutChatCapability,
    get_execution_context,
    reset_request_id,
    set_request_id,
)


class StructuredLogRecord(logging.LogRecord):
    """Log record containing provider lifecycle fields."""

    event: str
    request_id: str
    execution_id: str
    capability: str
    provider: str
    model: str
    streaming: bool
    duration_ms: float
    error_code: str
    cancellation_reason: str


class RecordHandler(logging.Handler):
    """Capture structured log records for assertions."""

    def __init__(self) -> None:
        """Initialize the record handler."""
        super().__init__()
        self.records: list[StructuredLogRecord] = []

    def emit(
        self,
        record: logging.LogRecord,
    ) -> None:
        """Capture a log record."""
        self.records.append(
            cast(StructuredLogRecord, record),
        )


class SuccessfulChatProvider:
    """Return deterministic responses while recording active context."""

    def __init__(self) -> None:
        """Initialize recorded execution contexts."""
        self.complete_context: ExecutionContext | None = None
        self.stream_contexts: list[ExecutionContext] = []

    async def complete(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        """Return a normalized completion."""
        await asyncio.sleep(0)
        self.complete_context = get_execution_context()

        return create_response(request)

    async def stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[ChatStreamEvent]:
        """Return a normalized successful stream."""
        self.stream_contexts.append(
            get_execution_context(),
        )

        yield ChatStreamStartEvent(
            id="provider-stream-123",
            provider="test-provider",
            model=request.model,
        )

        await asyncio.sleep(0)

        self.stream_contexts.append(
            get_execution_context(),
        )

        yield ChatStreamDeltaEvent(
            id="provider-stream-123",
            content="Hello.",
        )
        yield ChatStreamEndEvent(
            id="provider-stream-123",
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(
                input_tokens=1,
                output_tokens=1,
                total_tokens=2,
            ),
        )


class ErrorEventChatProvider(SuccessfulChatProvider):
    """Return a normalized provider streaming error event."""

    async def stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[ChatStreamEvent]:
        """Yield a normalized provider error event."""
        _ = request

        yield ChatStreamErrorEvent(
            id=None,
            code="provider_rate_limited",
            message="The selected provider is rate limited.",
        )


class RaisingStream(AsyncIterator[ChatStreamEvent]):
    """Raise a configured exception during asynchronous iteration."""

    def __init__(
        self,
        error: Exception,
    ) -> None:
        """Initialize the stream failure."""
        self._error = error

    def __aiter__(self) -> Self:
        """Return this asynchronous iterator."""
        return self

    async def __anext__(self) -> ChatStreamEvent:
        """Raise the configured stream failure."""
        await asyncio.sleep(0)
        raise self._error


class RaisingChatProvider:
    """Raise a configured error from every execution mode."""

    def __init__(
        self,
        error: Exception,
    ) -> None:
        """Initialize the provider failure."""
        self._error = error

    async def complete(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        """Raise the configured completion failure."""
        _ = request
        raise self._error

    def stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[ChatStreamEvent]:
        """Return an iterator that raises the configured failure."""
        _ = request
        return RaisingStream(self._error)


class CancellingChatProvider:
    """Expose deterministic completion and stream cancellation paths."""

    def __init__(self) -> None:
        """Initialize stream finalization state."""
        self.stream_closed = False

    async def complete(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        """Cancel non-streaming execution."""
        _ = request
        raise CancelledError

    async def stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[ChatStreamEvent]:
        """Yield once and record prompt iterator finalization."""
        try:
            yield ChatStreamStartEvent(
                id="cancelling-provider-stream",
                provider="test-provider",
                model=request.model,
            )
            await asyncio.Event().wait()
        finally:
            self.stream_closed = True


class SlowTimeoutChatProvider:
    """Delay execution until Trussium's configured timeout expires."""

    def __init__(self) -> None:
        """Initialize stream finalization state."""
        self.stream_closed = False

    async def complete(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        """Delay a non-streaming provider request."""
        await asyncio.sleep(1)
        return create_response(request)

    async def stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[ChatStreamEvent]:
        """Start a provider stream and then stop producing events."""
        try:
            yield ChatStreamStartEvent(
                id="timeout-provider-stream",
                provider="test-provider",
                model=request.model,
            )
            await asyncio.sleep(1)
        finally:
            self.stream_closed = True


def create_test_logger() -> tuple[
    logging.Logger,
    RecordHandler,
]:
    """Create an isolated context-aware logger."""
    logger = logging.getLogger(
        "trussium.tests.provider-logging",
    )
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False

    handler = RecordHandler()
    handler.addFilter(
        RuntimeContextFilter(),
    )
    logger.addHandler(handler)

    return logger, handler


def create_request(
    *,
    streaming: bool = False,
) -> ChatCompletionRequest:
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


def create_response(
    request: ChatCompletionRequest,
) -> ChatCompletionResponse:
    """Create a normalized chat response."""
    return ChatCompletionResponse(
        id="provider-response-123",
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


async def collect_events(
    events: AsyncIterator[ChatStreamEvent],
) -> list[ChatStreamEvent]:
    """Collect a provider stream into a list."""
    return [event async for event in events]


def create_capability_error() -> CapabilityExecutionError:
    """Create a normalized provider test failure."""
    return CapabilityExecutionError(
        code="provider_rate_limited",
        message="The selected provider is rate limited.",
        category=CapabilityErrorCategory.RATE_LIMITED,
    )


def test_provider_logging_decorator_implements_chat_capability() -> None:
    """The decorator should preserve the provider-neutral protocol."""
    capability = LoggingProviderChatCapability(
        SuccessfulChatProvider(),
        provider="test-provider",
    )

    assert isinstance(capability, ChatCapability)


@pytest.mark.parametrize(
    "provider",
    [
        "",
        "   ",
    ],
)
def test_provider_logging_decorator_rejects_empty_provider(
    provider: str,
) -> None:
    """Provider identifiers should contain non-whitespace characters."""
    with pytest.raises(
        ValueError,
        match="Provider name must not be empty",
    ):
        LoggingProviderChatCapability(
            SuccessfulChatProvider(),
            provider=provider,
        )


def test_nested_non_streaming_execution_logs_ordered_lifecycles() -> None:
    """Capability logging should remain outside provider logging."""
    logger, handler = create_test_logger()
    decorated_provider = SuccessfulChatProvider()
    provider = LoggingProviderChatCapability(
        decorated_provider,
        provider=" test-provider ",
        logger=logger,
    )
    capability = LoggingChatCapability(
        provider,
        logger=logger,
    )
    request = create_request()
    context_token = set_request_id(
        "request-123",
        execution_id="execution-123",
    )

    try:
        response = asyncio.run(
            capability.complete(request),
        )

        assert get_execution_context() == ExecutionContext(
            request_id="request-123",
            execution_id="execution-123",
        )
    finally:
        reset_request_id(context_token)

    assert response == create_response(request)
    assert decorated_provider.complete_context == ExecutionContext(
        request_id="request-123",
        execution_id="execution-123",
        capability=CHAT_CAPABILITY_NAME,
        provider="test-provider",
        model="test-model",
    )
    assert [record.event for record in handler.records] == [
        "capability.execution.started",
        "provider.execution.started",
        "provider.execution.completed",
        "capability.execution.completed",
    ]

    started_record = handler.records[1]
    completed_record = handler.records[2]

    assert started_record.levelno == logging.INFO
    assert started_record.request_id == "request-123"
    assert started_record.execution_id == "execution-123"
    assert started_record.capability == CHAT_CAPABILITY_NAME
    assert started_record.provider == "test-provider"
    assert started_record.model == "test-model"
    assert started_record.streaming is False
    assert completed_record.streaming is False
    assert completed_record.duration_ms >= 0


def test_non_streaming_normalized_failure_logs_error_code() -> None:
    """A normalized provider failure should emit one failed event."""
    logger, handler = create_test_logger()
    error = create_capability_error()
    provider = LoggingProviderChatCapability(
        RaisingChatProvider(error),
        provider="test-provider",
        logger=logger,
    )

    with pytest.raises(CapabilityExecutionError) as raised_error:
        asyncio.run(
            provider.complete(create_request()),
        )

    assert raised_error.value is error
    assert [record.event for record in handler.records] == [
        "provider.execution.started",
        "provider.execution.failed",
    ]

    failure_record = handler.records[1]

    assert failure_record.levelno == logging.ERROR
    assert failure_record.provider == "test-provider"
    assert failure_record.error_code == "provider_rate_limited"
    assert failure_record.streaming is False
    assert failure_record.duration_ms >= 0
    assert failure_record.exc_info is None


def test_non_streaming_unexpected_failure_logs_exception() -> None:
    """An unexpected provider failure should preserve exception information."""
    logger, handler = create_test_logger()
    error = RuntimeError("Unexpected provider failure.")
    provider = LoggingProviderChatCapability(
        RaisingChatProvider(error),
        provider="test-provider",
        logger=logger,
    )

    with pytest.raises(RuntimeError) as raised_error:
        asyncio.run(
            provider.complete(create_request()),
        )

    assert raised_error.value is error

    failure_record = handler.records[1]

    assert failure_record.event == "provider.execution.failed"
    assert failure_record.error_code == UNEXPECTED_PROVIDER_ERROR_CODE
    assert failure_record.exc_info is not None


def test_streaming_execution_logs_full_iterator_lifecycle() -> None:
    """A successful provider stream should remain correlated until exhaustion."""
    logger, handler = create_test_logger()
    decorated_provider = SuccessfulChatProvider()
    provider = LoggingProviderChatCapability(
        decorated_provider,
        provider="test-provider",
        logger=logger,
    )
    capability = LoggingChatCapability(
        provider,
        logger=logger,
    )
    context_token = set_request_id(
        "request-stream-123",
        execution_id="execution-stream-123",
    )

    try:
        events = asyncio.run(
            collect_events(
                capability.stream(
                    create_request(streaming=True),
                )
            )
        )

        assert get_execution_context() == ExecutionContext(
            request_id="request-stream-123",
            execution_id="execution-stream-123",
        )
    finally:
        reset_request_id(context_token)

    assert [event.type for event in events] == [
        "start",
        "delta",
        "end",
    ]
    assert decorated_provider.stream_contexts == [
        ExecutionContext(
            request_id="request-stream-123",
            execution_id="execution-stream-123",
            capability=CHAT_CAPABILITY_NAME,
            provider="test-provider",
            model="test-model",
        ),
        ExecutionContext(
            request_id="request-stream-123",
            execution_id="execution-stream-123",
            capability=CHAT_CAPABILITY_NAME,
            provider="test-provider",
            model="test-model",
        ),
    ]
    assert [record.event for record in handler.records] == [
        "capability.execution.started",
        "provider.execution.started",
        "provider.execution.completed",
        "capability.execution.completed",
    ]
    assert handler.records[1].streaming is True
    assert handler.records[2].streaming is True
    assert handler.records[2].duration_ms >= 0


def test_streaming_error_event_logs_failed_without_completed() -> None:
    """A normalized error event should fail the provider lifecycle once."""
    logger, handler = create_test_logger()
    provider = LoggingProviderChatCapability(
        ErrorEventChatProvider(),
        provider="test-provider",
        logger=logger,
    )

    events = asyncio.run(
        collect_events(
            provider.stream(
                create_request(streaming=True),
            )
        )
    )

    assert len(events) == 1
    assert isinstance(events[0], ChatStreamErrorEvent)
    assert events[0].code == "provider_rate_limited"
    assert [record.event for record in handler.records] == [
        "provider.execution.started",
        "provider.execution.failed",
    ]
    assert handler.records[1].error_code == "provider_rate_limited"
    assert handler.records[1].streaming is True


def test_streaming_raised_normalized_failure_logs_error_code() -> None:
    """A raised normalized stream failure should emit one failed event."""
    logger, handler = create_test_logger()
    error = create_capability_error()
    provider = LoggingProviderChatCapability(
        RaisingChatProvider(error),
        provider="test-provider",
        logger=logger,
    )

    with pytest.raises(CapabilityExecutionError) as raised_error:
        asyncio.run(
            collect_events(
                provider.stream(
                    create_request(streaming=True),
                )
            )
        )

    assert raised_error.value is error
    assert [record.event for record in handler.records] == [
        "provider.execution.started",
        "provider.execution.failed",
    ]
    assert handler.records[1].error_code == "provider_rate_limited"
    assert handler.records[1].exc_info is None


def test_streaming_unexpected_failure_logs_exception() -> None:
    """An unexpected stream failure should preserve exception information."""
    logger, handler = create_test_logger()
    error = RuntimeError("Unexpected provider stream failure.")
    provider = LoggingProviderChatCapability(
        RaisingChatProvider(error),
        provider="test-provider",
        logger=logger,
    )

    with pytest.raises(RuntimeError) as raised_error:
        asyncio.run(
            collect_events(
                provider.stream(
                    create_request(streaming=True),
                )
            )
        )

    assert raised_error.value is error

    failure_record = handler.records[1]

    assert failure_record.event == "provider.execution.failed"
    assert failure_record.error_code == UNEXPECTED_PROVIDER_ERROR_CODE
    assert failure_record.streaming is True
    assert failure_record.exc_info is not None


def test_nested_non_streaming_cancellation_logs_and_reraises() -> None:
    """Cancellation should unwind provider and capability lifecycles in order."""
    logger, handler = create_test_logger()
    provider = LoggingProviderChatCapability(
        CancellingChatProvider(),
        provider="test-provider",
        logger=logger,
    )
    capability = LoggingChatCapability(
        provider,
        logger=logger,
    )

    with pytest.raises(CancelledError):
        asyncio.run(
            capability.complete(create_request()),
        )

    assert [record.event for record in handler.records] == [
        "capability.execution.started",
        "provider.execution.started",
        "provider.execution.cancelled",
        "capability.execution.cancelled",
    ]

    provider_cancelled, capability_cancelled = handler.records[2:]

    assert provider_cancelled.streaming is False
    assert capability_cancelled.streaming is False
    assert provider_cancelled.duration_ms >= 0
    assert capability_cancelled.duration_ms >= 0
    assert provider_cancelled.cancellation_reason == "task_cancelled"
    assert capability_cancelled.cancellation_reason == "task_cancelled"
    assert provider_cancelled.exc_info is None
    assert capability_cancelled.exc_info is None


def test_nested_stream_close_finalizes_provider_before_cancellation_logs() -> None:
    """Closing the outer stream should promptly close the provider iterator."""
    logger, handler = create_test_logger()
    decorated_provider = CancellingChatProvider()
    provider = LoggingProviderChatCapability(
        decorated_provider,
        provider="test-provider",
        logger=logger,
    )
    capability = LoggingChatCapability(
        provider,
        logger=logger,
    )
    context_token = set_request_id(
        "request-cancelled-stream-123",
        execution_id="execution-cancelled-stream-123",
    )

    async def consume_one_and_close() -> ChatStreamEvent:
        events = cast(
            AsyncGenerator[ChatStreamEvent, None],
            capability.stream(
                create_request(streaming=True),
            ),
        )
        event = await anext(events)
        await events.aclose()
        return event

    try:
        event = asyncio.run(consume_one_and_close())

        assert get_execution_context() == ExecutionContext(
            request_id="request-cancelled-stream-123",
            execution_id="execution-cancelled-stream-123",
        )
    finally:
        reset_request_id(context_token)

    assert isinstance(event, ChatStreamStartEvent)
    assert decorated_provider.stream_closed is True
    assert [record.event for record in handler.records] == [
        "capability.execution.started",
        "provider.execution.started",
        "provider.execution.cancelled",
        "capability.execution.cancelled",
    ]
    assert all(record.streaming is True for record in handler.records)
    assert all(record.request_id == "request-cancelled-stream-123" for record in handler.records)
    assert all(
        record.execution_id == "execution-cancelled-stream-123" for record in handler.records
    )


def test_nested_non_streaming_timeout_logs_failed_lifecycles() -> None:
    """A provider deadline should fail both correlated execution lifecycles."""
    logger, handler = create_test_logger()
    timed_provider = TimeoutChatCapability(
        SlowTimeoutChatProvider(),
        provider_request_seconds=0.001,
        stream_idle_seconds=1,
    )
    provider = LoggingProviderChatCapability(
        timed_provider,
        provider="test-provider",
        logger=logger,
    )
    capability = LoggingChatCapability(provider, logger=logger)

    with pytest.raises(CapabilityExecutionError) as error_info:
        asyncio.run(capability.complete(create_request()))

    assert error_info.value.code == PROVIDER_REQUEST_TIMEOUT_CODE
    assert [record.event for record in handler.records] == [
        "capability.execution.started",
        "provider.execution.started",
        "provider.execution.failed",
        "capability.execution.failed",
    ]
    assert handler.records[2].error_code == PROVIDER_REQUEST_TIMEOUT_CODE
    assert handler.records[3].error_code == PROVIDER_REQUEST_TIMEOUT_CODE


def test_nested_stream_timeout_logs_failed_lifecycles_and_closes_provider() -> None:
    """An idle provider stream should fail both lifecycles and close upstream."""
    logger, handler = create_test_logger()
    decorated_provider = SlowTimeoutChatProvider()
    timed_provider = TimeoutChatCapability(
        decorated_provider,
        provider_request_seconds=1,
        stream_idle_seconds=0.001,
    )
    provider = LoggingProviderChatCapability(
        timed_provider,
        provider="test-provider",
        logger=logger,
    )
    capability = LoggingChatCapability(provider, logger=logger)

    events = asyncio.run(
        collect_events(
            capability.stream(create_request(streaming=True)),
        )
    )

    assert [event.type for event in events] == ["start", "error"]
    assert events[-1].id == "timeout-provider-stream"
    assert decorated_provider.stream_closed is True
    assert [record.event for record in handler.records] == [
        "capability.execution.started",
        "provider.execution.started",
        "provider.execution.failed",
        "capability.execution.failed",
    ]
    assert handler.records[2].error_code == PROVIDER_STREAM_TIMEOUT_CODE
    assert handler.records[3].error_code == PROVIDER_STREAM_TIMEOUT_CODE
