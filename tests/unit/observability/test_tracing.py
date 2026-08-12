"""Tests for application-scoped OpenTelemetry tracing."""

import asyncio
import io
import json
from collections.abc import AsyncIterator, Sequence
from typing import cast
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode

from trussium.app import create_application
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
from trussium.config.settings import ObservabilitySettings, Settings
from trussium.observability import (
    LoggingChatCapability,
    LoggingProviderChatCapability,
    OperationalSpanExporter,
    RuntimeTracing,
    configure_logging,
)
from trussium.runtime.streaming import close_async_resource

_TRACE_ID = "0af7651916cd43dd8448eb211c80319c"
_PARENT_SPAN_ID = "b7ad6b7169203331"
_TRACEPARENT = f"00-{_TRACE_ID}-{_PARENT_SPAN_ID}-01"


class StubSpanExporter(SpanExporter):
    """Return or raise a configured result while recording lifecycle calls."""

    def __init__(
        self,
        result: SpanExportResult = SpanExportResult.SUCCESS,
        *,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.shutdown_calls = 0
        self.flush_timeouts: list[int] = []

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        _ = spans
        if self.error is not None:
            raise self.error
        return self.result

    def shutdown(self) -> None:
        self.shutdown_calls += 1

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        self.flush_timeouts.append(timeout_millis)
        return True


class StubChatCapability:
    """Return deterministic ordinary and streaming chat results."""

    async def complete(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        return ChatCompletionResponse(
            id="trace-response",
            provider="openai",
            model=request.model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(
                        role=ChatRole.ASSISTANT,
                        content="safe response",
                    ),
                    finish_reason=FinishReason.STOP,
                )
            ],
            usage=TokenUsage(
                input_tokens=1,
                output_tokens=2,
                total_tokens=3,
            ),
        )

    async def stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[ChatStreamEvent]:
        yield ChatStreamStartEvent(
            id="trace-stream",
            provider="openai",
            model=request.model,
        )
        yield ChatStreamDeltaEvent(
            id="trace-stream",
            content="safe response",
        )
        yield ChatStreamEndEvent(
            id="trace-stream",
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(
                input_tokens=1,
                output_tokens=2,
                total_tokens=3,
            ),
        )


class FailingChatCapability(StubChatCapability):
    """Raise an unexpected provider failure."""

    async def complete(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        _ = request
        raise RuntimeError("secret provider failure detail")


def _tracing_runtime() -> tuple[RuntimeTracing, InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    tracing = RuntimeTracing(
        ObservabilitySettings(
            tracing_enabled=True,
            tracing_service_name="trussium-test",
        ),
        span_processor=SimpleSpanProcessor(exporter),
    )
    return tracing, exporter


def _application(
    tracing: RuntimeTracing,
    capability: StubChatCapability | None = None,
) -> FastAPI:
    provider = LoggingProviderChatCapability(
        capability or StubChatCapability(),
        provider="openai",
        tracer=tracing.tracer,
    )
    chat = LoggingChatCapability(
        provider,
        tracer=tracing.tracer,
    )
    settings = Settings(
        observability=ObservabilitySettings(
            tracing_enabled=True,
            tracing_service_name="trussium-test",
        )
    )
    return create_application(
        settings,
        chat_capability=chat,
        tracing=tracing,
    )


def _request_payload(*, streaming: bool = False) -> dict[str, object]:
    return {
        "model": "trace-model",
        "messages": [
            {
                "role": "user",
                "content": "secret prompt must never enter spans",
            }
        ],
        "stream": streaming,
    }


def test_disabled_runtime_uses_noop_tracing() -> None:
    tracing = RuntimeTracing(ObservabilitySettings())

    assert tracing.enabled is False
    assert tracing.force_flush() is True

    tracing.shutdown()
    tracing.shutdown()


def test_operational_exporter_reports_failure_result() -> None:
    """Exporter failure results should create one bounded operational event."""
    output = io.StringIO()
    configure_logging(stream=output)
    exporter = StubSpanExporter(SpanExportResult.FAILURE)
    operational_exporter = OperationalSpanExporter(exporter)
    spans = (cast(ReadableSpan, object()),)

    result = operational_exporter.export(spans)

    assert result is SpanExportResult.FAILURE
    payload = json.loads(output.getvalue())
    assert payload["event"] == "observability.trace_export.failed"
    assert payload["error_code"] == "trace_export_failed"
    assert payload["span_count"] == 1
    assert "exception" not in payload


def test_operational_exporter_preserves_success_without_failure_event() -> None:
    """Successful exports should remain silent and preserve the wrapped result."""
    output = io.StringIO()
    configure_logging(stream=output)
    exporter = StubSpanExporter()

    result = OperationalSpanExporter(exporter).export(())

    assert result is SpanExportResult.SUCCESS
    assert output.getvalue() == ""


def test_operational_exporter_bounds_exception_details_and_delegates_lifecycle() -> None:
    """Exporter exceptions should not leak messages and lifecycle calls should delegate."""
    output = io.StringIO()
    configure_logging(stream=output)
    exporter = StubSpanExporter(error=RuntimeError("secret collector response"))
    operational_exporter = OperationalSpanExporter(exporter)

    result = operational_exporter.export(())
    flushed = operational_exporter.force_flush(1234)
    operational_exporter.shutdown()

    assert result is SpanExportResult.FAILURE
    assert flushed is True
    assert exporter.flush_timeouts == [1234]
    assert exporter.shutdown_calls == 1
    payload = json.loads(output.getvalue())
    assert payload["event"] == "observability.trace_export.failed"
    assert payload["error_type"] == "RuntimeError"
    assert payload["span_count"] == 0
    assert "secret collector response" not in output.getvalue()


def test_application_shutdown_closes_owned_span_processor_once() -> None:
    processor = MagicMock(spec=SpanProcessor)
    tracing = RuntimeTracing(
        ObservabilitySettings(tracing_enabled=True),
        span_processor=processor,
    )

    with TestClient(_application(tracing)) as client:
        assert client.get("/health/live").status_code == 200

    tracing.shutdown()

    processor.shutdown.assert_called_once_with()


def test_request_creates_nested_spans_with_inbound_remote_parent() -> None:
    tracing, exporter = _tracing_runtime()

    with TestClient(_application(tracing)) as client:
        response = client.post(
            "/v1/chat/completions",
            headers={
                "X-Request-ID": "trace-request-123",
                "traceparent": _TRACEPARENT,
            },
            json=_request_payload(),
        )

    assert response.status_code == 200
    spans = {span.name: span for span in exporter.get_finished_spans()}
    assert set(spans) == {
        "HTTP POST",
        "trussium.capability.chat",
        "trussium.provider.chat",
    }

    server = spans["HTTP POST"]
    capability = spans["trussium.capability.chat"]
    provider = spans["trussium.provider.chat"]

    assert server.kind is SpanKind.SERVER
    assert capability.kind is SpanKind.INTERNAL
    assert provider.kind is SpanKind.CLIENT
    assert f"{server.context.trace_id:032x}" == _TRACE_ID
    assert server.parent is not None
    assert f"{server.parent.span_id:016x}" == _PARENT_SPAN_ID
    assert capability.parent is not None
    assert capability.parent.span_id == server.context.span_id
    assert provider.parent is not None
    assert provider.parent.span_id == capability.context.span_id
    assert server.attributes is not None
    assert server.attributes["http.request.method"] == "POST"
    assert server.attributes["http.route"] == "/v1/chat/completions"
    assert server.attributes["http.response.status_code"] == 200
    assert server.attributes["trussium.request_id"] == "trace-request-123"
    assert capability.attributes is not None
    assert capability.attributes["trussium.capability"] == "chat.completions"
    assert capability.attributes["gen_ai.request.model"] == "trace-model"
    assert provider.attributes is not None
    assert provider.attributes["trussium.provider"] == "openai"
    assert provider.attributes["trussium.outcome"] == "completed"
    assert "secret prompt" not in repr(exporter.get_finished_spans())


def test_streaming_spans_cover_the_terminal_response() -> None:
    tracing, exporter = _tracing_runtime()

    with TestClient(_application(tracing)) as client:
        response = client.post(
            "/v1/chat/completions",
            json=_request_payload(streaming=True),
        )

    assert response.status_code == 200
    assert "event: end" in response.text
    spans = exporter.get_finished_spans()
    assert len(spans) == 3

    for span in spans:
        assert span.end_time is not None
        assert span.attributes is not None
        assert span.attributes["trussium.outcome"] == "completed"

        if span.name != "HTTP POST":
            assert span.attributes["trussium.streaming"] is True


def test_partially_consumed_stream_keeps_spans_open_until_close() -> None:
    tracing, exporter = _tracing_runtime()
    provider = LoggingProviderChatCapability(
        StubChatCapability(),
        provider="openai",
        tracer=tracing.tracer,
    )
    capability = LoggingChatCapability(
        provider,
        tracer=tracing.tracer,
    )
    request = ChatCompletionRequest.model_validate(_request_payload(streaming=True))

    async def consume_and_close() -> None:
        events = capability.stream(request)
        await anext(events)
        assert exporter.get_finished_spans() == ()
        await close_async_resource(events)

    asyncio.run(consume_and_close())

    spans = exporter.get_finished_spans()
    assert len(spans) == 2

    for span in spans:
        assert span.attributes is not None
        assert span.attributes["trussium.outcome"] == "cancelled"
        assert span.status.status_code is StatusCode.ERROR

    tracing.shutdown()


def test_failed_request_marks_all_spans_without_sensitive_error_message() -> None:
    tracing, exporter = _tracing_runtime()

    with TestClient(
        _application(tracing, FailingChatCapability()),
        raise_server_exceptions=False,
    ) as client:
        response = client.post(
            "/v1/chat/completions",
            json=_request_payload(),
        )

    assert response.status_code == 500
    spans = exporter.get_finished_spans()
    assert len(spans) == 3
    assert all(span.status.status_code is StatusCode.ERROR for span in spans)
    assert "secret provider failure detail" not in repr(spans)


def test_health_and_metrics_endpoints_are_excluded() -> None:
    tracing, exporter = _tracing_runtime()

    with TestClient(_application(tracing)) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200
        assert client.get("/metrics").status_code == 200

    assert exporter.get_finished_spans() == ()
