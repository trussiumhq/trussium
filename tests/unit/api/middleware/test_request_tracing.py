"""Tests for OpenTelemetry request cancellation instrumentation."""

import asyncio
from asyncio import CancelledError
from typing import cast

import pytest
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode
from starlette.requests import ClientDisconnect
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from trussium.config.settings import ObservabilitySettings
from trussium.middleware import RequestLoggingMiddleware, RequestTracingMiddleware
from trussium.observability import RuntimeTracing
from trussium.runtime import reset_request_id, set_request_id


def _http_scope() -> Scope:
    return cast(
        Scope,
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/v1/chat/completions",
            "raw_path": b"/v1/chat/completions",
            "query_string": b"secret=query",
            "root_path": "",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 9000),
        },
    )


def _runtime() -> tuple[RuntimeTracing, InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    tracing = RuntimeTracing(
        ObservabilitySettings(tracing_enabled=True),
        span_processor=SimpleSpanProcessor(exporter),
    )
    return tracing, exporter


async def _receive() -> Message:
    return {
        "type": "http.request",
        "body": b"secret body",
        "more_body": False,
    }


def test_send_disconnect_is_recorded_when_logging_suppresses_exception() -> None:
    """The outer span should retain a disconnect observed by its send wrapper."""
    tracing, exporter = _runtime()

    async def application(
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        _ = (scope, receive)
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [],
            }
        )

    async def disconnected_send(message: Message) -> None:
        _ = message
        raise ClientDisconnect

    middleware = RequestTracingMiddleware(
        RequestLoggingMiddleware(cast(ASGIApp, application)),
        tracer=tracing.tracer,
    )
    token = set_request_id(
        "disconnect-request",
        execution_id="disconnect-execution",
    )

    try:
        asyncio.run(middleware(_http_scope(), _receive, disconnected_send))
    finally:
        reset_request_id(token)

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.attributes is not None
    assert span.attributes["trussium.outcome"] == "cancelled"
    assert span.attributes["trussium.cancellation_reason"] == "client_disconnect"
    assert span.attributes["trussium.request_id"] == "disconnect-request"
    assert span.status.status_code is StatusCode.ERROR
    assert "secret=query" not in repr(span)
    assert "secret body" not in repr(span)

    tracing.shutdown()


def test_task_cancellation_ends_span_and_propagates() -> None:
    """Task cancellation should end the span while preserving cancellation."""
    tracing, exporter = _runtime()

    async def application(
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        _ = (scope, receive, send)
        raise CancelledError

    async def send(message: Message) -> None:
        _ = message

    middleware = RequestTracingMiddleware(
        cast(ASGIApp, application),
        tracer=tracing.tracer,
    )

    with pytest.raises(CancelledError):
        asyncio.run(middleware(_http_scope(), _receive, send))

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.attributes is not None
    assert span.attributes["trussium.outcome"] == "cancelled"
    assert span.attributes["trussium.cancellation_reason"] == "task_cancelled"
    assert span.status.status_code is StatusCode.ERROR

    tracing.shutdown()
