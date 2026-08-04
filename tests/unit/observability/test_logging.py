"""Tests for structured logging."""

import io
import json
import logging

from trussium.observability import (
    StructuredJsonFormatter,
    configure_logging,
    get_logger,
)


def test_structured_formatter_returns_valid_json() -> None:
    """The formatter should produce valid structured JSON."""
    formatter = StructuredJsonFormatter()

    record = logging.LogRecord(
        name="trussium.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Test message",
        args=(),
        exc_info=None,
    )

    record.event = "test.event"
    record.request_id = "request-123"
    record.http_method = "GET"
    record.http_path = "/test"
    record.http_status_code = 200
    record.duration_ms = 12.5

    formatted = formatter.format(record)
    payload = json.loads(formatted)

    assert payload["level"] == "INFO"
    assert payload["logger"] == "trussium.test"
    assert payload["message"] == "Test message"
    assert payload["event"] == "test.event"
    assert payload["request_id"] == "request-123"
    assert payload["http_method"] == "GET"
    assert payload["http_path"] == "/test"
    assert payload["http_status_code"] == 200
    assert payload["duration_ms"] == 12.5
    assert isinstance(payload["timestamp"], str)


def test_configure_logging_outputs_json() -> None:
    """Configured Trussium loggers should emit JSON."""
    output = io.StringIO()

    configure_logging(
        stream=output,
    )

    logger = get_logger("test")
    logger.info(
        "Configured log message",
        extra={
            "event": "test.configured",
            "request_id": "request-456",
        },
    )

    payload = json.loads(
        output.getvalue(),
    )

    assert payload["logger"] == "trussium.test"
    assert payload["message"] == "Configured log message"
    assert payload["event"] == "test.configured"
    assert payload["request_id"] == "request-456"


def test_configure_logging_is_idempotent() -> None:
    """Repeated configuration should not duplicate handlers."""
    first_output = io.StringIO()
    second_output = io.StringIO()

    configure_logging(
        stream=first_output,
    )
    configure_logging(
        stream=second_output,
    )

    logger = get_logger("test")
    logger.info(
        "Single message",
    )

    assert first_output.getvalue() == ""
    assert (
        second_output.getvalue().count(
            "Single message",
        )
        == 1
    )


def test_get_logger_applies_trussium_namespace() -> None:
    """Component loggers should use the Trussium namespace."""
    logger = get_logger("http")

    assert logger.name == "trussium.http"
