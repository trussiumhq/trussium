"""Tests for structured capability execution logging."""

import asyncio
import logging
from collections.abc import AsyncIterator
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
    UNEXPECTED_CAPABILITY_ERROR_CODE,
    LoggingChatCapability,
    RuntimeContextFilter,
)
from trussium.runtime import (
    ExecutionContext,
    get_execution_context,
    reset_request_id,
    set_request_id,
)


class StructuredLogRecord(logging.LogRecord):
    """Log record containing capability lifecycle fields."""

    event: str
    request_id: str
    execution_id: str
    capability: str
    model: str
    streaming: bool
    duration_ms: float
    error_code: str


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


class SuccessfulChatCapability:
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
            id="chat-stream-123",
            provider="stub",
            model=request.model,
        )

        await asyncio.sleep(0)

        self.stream_contexts.append(
            get_execution_context(),
        )

        yield ChatStreamDeltaEvent(
            id="chat-stream-123",
            content="Hello.",
        )
        yield ChatStreamEndEvent(
            id="chat-stream-123",
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(
                input_tokens=1,
                output_tokens=1,
                total_tokens=2,
            ),
        )


class ErrorEventChatCapability(SuccessfulChatCapability):
    """Return a normalized streaming error event."""

    async def stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[ChatStreamEvent]:
        """Yield a normalized capability error event."""
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


class RaisingChatCapability:
    """Raise a configured error from every execution mode."""

    def __init__(
        self,
        error: Exception,
    ) -> None:
        """Initialize the capability failure."""
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


def create_test_logger() -> tuple[
    logging.Logger,
    RecordHandler,
]:
    """Create an isolated context-aware logger."""
    logger = logging.getLogger(
        "trussium.tests.capability-logging",
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
        id="chat-123",
        provider="stub",
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
    """Collect a capability stream into a list."""
    return [event async for event in events]


def create_capability_error() -> CapabilityExecutionError:
    """Create a normalized test failure."""
    return CapabilityExecutionError(
        code="provider_rate_limited",
        message="The selected provider is rate limited.",
        category=CapabilityErrorCategory.RATE_LIMITED,
    )


def test_logging_decorator_implements_chat_capability() -> None:
    """The decorator should preserve the provider-neutral protocol."""
    capability = LoggingChatCapability(
        SuccessfulChatCapability(),
    )

    assert isinstance(capability, ChatCapability)


def test_non_streaming_execution_logs_started_and_completed() -> None:
    """A successful completion should emit a correlated lifecycle."""
    logger, handler = create_test_logger()
    decorated_capability = SuccessfulChatCapability()
    capability = LoggingChatCapability(
        decorated_capability,
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
    assert decorated_capability.complete_context == ExecutionContext(
        request_id="request-123",
        execution_id="execution-123",
        capability=CHAT_CAPABILITY_NAME,
        model="test-model",
    )
    assert [record.event for record in handler.records] == [
        "capability.execution.started",
        "capability.execution.completed",
    ]

    started_record, completed_record = handler.records

    assert started_record.levelno == logging.INFO
    assert started_record.request_id == "request-123"
    assert started_record.execution_id == "execution-123"
    assert started_record.capability == CHAT_CAPABILITY_NAME
    assert started_record.model == "test-model"
    assert started_record.streaming is False
    assert completed_record.streaming is False
    assert completed_record.duration_ms >= 0


def test_non_streaming_normalized_failure_logs_error_code() -> None:
    """A normalized completion failure should emit one failed event."""
    logger, handler = create_test_logger()
    error = create_capability_error()
    capability = LoggingChatCapability(
        RaisingChatCapability(error),
        logger=logger,
    )

    with pytest.raises(CapabilityExecutionError) as raised_error:
        asyncio.run(
            capability.complete(create_request()),
        )

    assert raised_error.value is error
    assert [record.event for record in handler.records] == [
        "capability.execution.started",
        "capability.execution.failed",
    ]

    failure_record = handler.records[1]

    assert failure_record.levelno == logging.ERROR
    assert failure_record.error_code == "provider_rate_limited"
    assert failure_record.streaming is False
    assert failure_record.duration_ms >= 0
    assert failure_record.exc_info is None


def test_non_streaming_unexpected_failure_logs_exception() -> None:
    """An unexpected completion failure should preserve exception information."""
    logger, handler = create_test_logger()
    error = RuntimeError("Unexpected test failure.")
    capability = LoggingChatCapability(
        RaisingChatCapability(error),
        logger=logger,
    )

    with pytest.raises(RuntimeError) as raised_error:
        asyncio.run(
            capability.complete(create_request()),
        )

    assert raised_error.value is error

    failure_record = handler.records[1]

    assert failure_record.event == "capability.execution.failed"
    assert failure_record.error_code == UNEXPECTED_CAPABILITY_ERROR_CODE
    assert failure_record.exc_info is not None


def test_streaming_execution_logs_full_iterator_lifecycle() -> None:
    """A successful stream should remain correlated until exhaustion."""
    logger, handler = create_test_logger()
    decorated_capability = SuccessfulChatCapability()
    capability = LoggingChatCapability(
        decorated_capability,
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
    assert decorated_capability.stream_contexts == [
        ExecutionContext(
            request_id="request-stream-123",
            execution_id="execution-stream-123",
            capability=CHAT_CAPABILITY_NAME,
            model="test-model",
        ),
        ExecutionContext(
            request_id="request-stream-123",
            execution_id="execution-stream-123",
            capability=CHAT_CAPABILITY_NAME,
            model="test-model",
        ),
    ]
    assert [record.event for record in handler.records] == [
        "capability.execution.started",
        "capability.execution.completed",
    ]
    assert all(record.streaming is True for record in handler.records)
    assert handler.records[1].duration_ms >= 0


def test_streaming_error_event_logs_failed_without_completed() -> None:
    """A normalized error event should fail the stream lifecycle once."""
    logger, handler = create_test_logger()
    capability = LoggingChatCapability(
        ErrorEventChatCapability(),
        logger=logger,
    )

    events = asyncio.run(
        collect_events(
            capability.stream(
                create_request(streaming=True),
            )
        )
    )

    assert len(events) == 1
    assert isinstance(events[0], ChatStreamErrorEvent)
    assert events[0].code == "provider_rate_limited"
    assert [record.event for record in handler.records] == [
        "capability.execution.started",
        "capability.execution.failed",
    ]
    assert handler.records[1].error_code == "provider_rate_limited"
    assert handler.records[1].streaming is True


def test_streaming_raised_normalized_failure_logs_error_code() -> None:
    """A raised normalized stream failure should emit one failed event."""
    logger, handler = create_test_logger()
    error = create_capability_error()
    capability = LoggingChatCapability(
        RaisingChatCapability(error),
        logger=logger,
    )

    with pytest.raises(CapabilityExecutionError) as raised_error:
        asyncio.run(
            collect_events(
                capability.stream(
                    create_request(streaming=True),
                )
            )
        )

    assert raised_error.value is error
    assert [record.event for record in handler.records] == [
        "capability.execution.started",
        "capability.execution.failed",
    ]
    assert handler.records[1].error_code == "provider_rate_limited"
    assert handler.records[1].exc_info is None


def test_streaming_unexpected_failure_logs_exception() -> None:
    """An unexpected stream failure should preserve exception information."""
    logger, handler = create_test_logger()
    error = RuntimeError("Unexpected stream failure.")
    capability = LoggingChatCapability(
        RaisingChatCapability(error),
        logger=logger,
    )

    with pytest.raises(RuntimeError) as raised_error:
        asyncio.run(
            collect_events(
                capability.stream(
                    create_request(streaming=True),
                )
            )
        )

    assert raised_error.value is error

    failure_record = handler.records[1]

    assert failure_record.event == "capability.execution.failed"
    assert failure_record.error_code == UNEXPECTED_CAPABILITY_ERROR_CODE
    assert failure_record.streaming is True
    assert failure_record.exc_info is not None
