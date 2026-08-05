"""Tests for structured request logging."""

import logging
from collections.abc import AsyncIterator
from typing import cast
from uuid import UUID

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from trussium.middleware import (
    REQUEST_ID_HEADER,
    RequestCorrelationMiddleware,
    RequestLoggingMiddleware,
)
from trussium.observability import RuntimeContextFilter
from trussium.runtime import get_execution_context


class StructuredLogRecord(logging.LogRecord):
    """Log record containing Trussium structured fields."""

    event: str
    request_id: str | None
    execution_id: str
    http_method: str
    http_path: str
    http_status_code: int
    duration_ms: float


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
        """Capture a log record.

        Args:
            record: Emitted log record.
        """
        self.records.append(
            cast(StructuredLogRecord, record),
        )


def create_test_logger() -> tuple[
    logging.Logger,
    RecordHandler,
]:
    """Create an isolated logger and context-aware record handler."""
    logger = logging.getLogger(
        "trussium.tests.request-logging",
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


def create_test_application(
    logger: logging.Logger,
) -> FastAPI:
    """Create a test application with request lifecycle middleware."""
    application = FastAPI()

    application.add_middleware(
        RequestLoggingMiddleware,
        logger=logger,
    )
    application.add_middleware(
        RequestCorrelationMiddleware,
    )

    @application.get("/success")
    async def success() -> dict[str, str]:
        """Return a successful response."""
        return {
            "status": "ok",
        }

    @application.get("/error")
    async def error() -> None:
        """Raise a handled HTTP error."""
        raise HTTPException(
            status_code=status.HTTP_418_IM_A_TEAPOT,
            detail="Test error.",
        )

    @application.get("/failure")
    async def failure() -> None:
        """Raise an unhandled execution failure."""
        raise RuntimeError("Test failure.")

    @application.get("/stream")
    async def stream() -> StreamingResponse:
        """Return active execution IDs from a streaming response."""

        async def generate() -> AsyncIterator[str]:
            yield str(get_execution_context().execution_id)

        return StreamingResponse(
            content=generate(),
            media_type="text/plain",
        )

    return application


def test_request_lifecycle_logs_include_execution_context() -> None:
    """Started and completed events should inherit the same execution ID."""
    logger, handler = create_test_logger()
    client = TestClient(
        create_test_application(logger),
    )

    response = client.get(
        "/success",
        headers={
            REQUEST_ID_HEADER: "request-123",
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert len(handler.records) == 2

    started_record, completed_record = handler.records

    assert started_record.event == "http.request.started"
    assert completed_record.event == "http.request.completed"
    assert started_record.request_id == "request-123"
    assert completed_record.request_id == "request-123"
    assert started_record.execution_id == completed_record.execution_id
    assert str(UUID(started_record.execution_id)) == started_record.execution_id
    assert completed_record.http_status_code == status.HTTP_200_OK
    assert completed_record.duration_ms >= 0


def test_request_logging_uses_generated_request_id() -> None:
    """Lifecycle events should include a generated request identifier."""
    logger, handler = create_test_logger()
    client = TestClient(
        create_test_application(logger),
    )

    response = client.get("/success")

    assert response.status_code == status.HTTP_200_OK

    request_id = response.headers[REQUEST_ID_HEADER]

    assert str(UUID(request_id)) == request_id
    assert all(record.request_id == request_id for record in handler.records)


def test_handled_http_error_emits_completed_event() -> None:
    """Handled HTTP errors should retain normal completion logging."""
    logger, handler = create_test_logger()
    client = TestClient(
        create_test_application(logger),
    )

    response = client.get(
        "/error",
        headers={
            REQUEST_ID_HEADER: "request-error-123",
        },
    )

    assert response.status_code == status.HTTP_418_IM_A_TEAPOT
    assert [record.event for record in handler.records] == [
        "http.request.started",
        "http.request.completed",
    ]
    assert handler.records[1].http_status_code == status.HTTP_418_IM_A_TEAPOT


def test_unhandled_failure_emits_failed_event() -> None:
    """Unhandled exceptions should emit a correlated failure event."""
    logger, handler = create_test_logger()
    client = TestClient(
        create_test_application(logger),
        raise_server_exceptions=False,
    )

    response = client.get(
        "/failure",
        headers={
            REQUEST_ID_HEADER: "request-failure-123",
        },
    )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert [record.event for record in handler.records] == [
        "http.request.started",
        "http.request.failed",
    ]

    failure_record = handler.records[1]

    assert failure_record.request_id == "request-failure-123"
    assert failure_record.http_status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert failure_record.exc_info is not None


def test_streaming_lifecycle_retains_execution_context() -> None:
    """Execution context should remain active until streaming completes."""
    logger, handler = create_test_logger()
    client = TestClient(
        create_test_application(logger),
    )

    with client.stream(
        "GET",
        "/stream",
        headers={
            REQUEST_ID_HEADER: "request-stream-123",
        },
    ) as response:
        streamed_execution_id = "".join(response.iter_text())

        assert response.status_code == status.HTTP_200_OK

    assert len(handler.records) == 2

    started_record, completed_record = handler.records

    assert started_record.execution_id == streamed_execution_id
    assert completed_record.execution_id == streamed_execution_id
    assert completed_record.http_status_code == status.HTTP_200_OK
