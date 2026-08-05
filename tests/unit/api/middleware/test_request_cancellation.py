"""Tests for HTTP client-disconnect and request cancellation logging."""

import asyncio
import logging
from asyncio import CancelledError
from collections.abc import AsyncIterator
from typing import cast

import pytest
from starlette.requests import ClientDisconnect
from starlette.types import (
    ASGIApp,
    Message,
    Receive,
    Scope,
    Send,
)

from trussium.api.sse import ClosableStreamingResponse
from trussium.middleware import RequestLoggingMiddleware
from trussium.observability import RuntimeContextFilter
from trussium.runtime import reset_request_id, set_request_id


class CancellationLogRecord(logging.LogRecord):
    """Log record containing request cancellation fields."""

    event: str
    request_id: str
    execution_id: str
    http_method: str
    http_path: str
    http_status_code: int
    duration_ms: float
    cancellation_reason: str


class RecordHandler(logging.Handler):
    """Capture structured cancellation log records."""

    def __init__(self) -> None:
        """Initialize the record handler."""
        super().__init__()
        self.records: list[CancellationLogRecord] = []

    def emit(
        self,
        record: logging.LogRecord,
    ) -> None:
        """Capture a log record."""
        self.records.append(
            cast(CancellationLogRecord, record),
        )


def create_test_logger() -> tuple[
    logging.Logger,
    RecordHandler,
]:
    """Create an isolated context-aware request logger."""
    logger = logging.getLogger(
        "trussium.tests.request-cancellation",
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


def create_http_scope(
    *,
    spec_version: str,
) -> Scope:
    """Create a minimal HTTP ASGI scope."""
    return cast(
        Scope,
        {
            "type": "http",
            "asgi": {
                "version": "3.0",
                "spec_version": spec_version,
            },
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/v1/chat/completions",
            "raw_path": b"/v1/chat/completions",
            "query_string": b"",
            "root_path": "",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 9000),
        },
    )


def test_asgi_23_disconnect_cancels_and_finalizes_stream() -> None:
    """An ASGI disconnect should finalize the stream before terminal logging."""
    logger, handler = create_test_logger()
    stream_finalized = asyncio.Event()
    response_body_sent = asyncio.Event()

    async def generate() -> AsyncIterator[str]:
        try:
            yield "first"
            await asyncio.Event().wait()
        finally:
            stream_finalized.set()

    response = ClosableStreamingResponse(
        generate(),
        media_type="text/event-stream",
    )

    async def application(
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        await response(scope, receive, send)

    middleware = RequestLoggingMiddleware(
        cast(ASGIApp, application),
        logger=logger,
    )

    async def receive() -> Message:
        await response_body_sent.wait()
        return {
            "type": "http.disconnect",
        }

    async def send(message: Message) -> None:
        if message["type"] == "http.response.body" and message.get("more_body") is True:
            response_body_sent.set()

    context_token = set_request_id(
        "request-disconnect-123",
        execution_id="execution-disconnect-123",
    )

    try:
        asyncio.run(
            middleware(
                create_http_scope(spec_version="2.3"),
                receive,
                send,
            )
        )
    finally:
        reset_request_id(context_token)

    assert stream_finalized.is_set()
    assert [record.event for record in handler.records] == [
        "http.request.started",
        "http.request.cancelled",
    ]

    cancelled_record = handler.records[1]

    assert cancelled_record.levelno == logging.INFO
    assert cancelled_record.request_id == "request-disconnect-123"
    assert cancelled_record.execution_id == "execution-disconnect-123"
    assert cancelled_record.http_method == "POST"
    assert cancelled_record.http_path == "/v1/chat/completions"
    assert cancelled_record.http_status_code == 200
    assert cancelled_record.duration_ms >= 0
    assert cancelled_record.cancellation_reason == "client_disconnect"
    assert cancelled_record.exc_info is None


def test_asgi_24_client_disconnect_is_suppressed_and_logged() -> None:
    """A Starlette send disconnect should be an expected terminal event."""
    logger, handler = create_test_logger()

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
        raise ClientDisconnect

    async def receive() -> Message:
        return {
            "type": "http.request",
            "body": b"",
            "more_body": False,
        }

    async def send(message: Message) -> None:
        _ = message

    middleware = RequestLoggingMiddleware(
        cast(ASGIApp, application),
        logger=logger,
    )

    asyncio.run(
        middleware(
            create_http_scope(spec_version="2.4"),
            receive,
            send,
        )
    )

    assert [record.event for record in handler.records] == [
        "http.request.started",
        "http.request.cancelled",
    ]
    assert handler.records[1].http_status_code == 200
    assert handler.records[1].cancellation_reason == "client_disconnect"
    assert handler.records[1].exc_info is None


def test_outer_task_cancellation_is_logged_and_reraised() -> None:
    """Cooperative task cancellation should remain visible to the caller."""
    logger, handler = create_test_logger()
    application_started = asyncio.Event()

    async def application(
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        _ = (scope, receive, send)
        application_started.set()
        await asyncio.Event().wait()

    async def receive() -> Message:
        return {
            "type": "http.request",
            "body": b"",
            "more_body": False,
        }

    async def send(message: Message) -> None:
        _ = message

    middleware = RequestLoggingMiddleware(
        cast(ASGIApp, application),
        logger=logger,
    )

    async def run_and_cancel() -> None:
        task = asyncio.create_task(
            middleware(
                create_http_scope(spec_version="2.3"),
                receive,
                send,
            )
        )

        await application_started.wait()
        task.cancel()

        with pytest.raises(CancelledError):
            await task

    asyncio.run(run_and_cancel())

    assert [record.event for record in handler.records] == [
        "http.request.started",
        "http.request.cancelled",
    ]
    assert handler.records[1].cancellation_reason == "task_cancelled"
    assert handler.records[1].exc_info is None
