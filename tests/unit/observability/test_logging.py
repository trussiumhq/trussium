"""Tests for structured logging."""

import io
import json
import logging

from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from trussium.config.settings import ObservabilitySettings
from trussium.observability import (
    RuntimeContextFilter,
    RuntimeTracing,
    StructuredJsonFormatter,
    configure_logging,
    get_logger,
)
from trussium.runtime import (
    bind_execution_context,
    reset_request_id,
    set_request_id,
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
    record.execution_id = "execution-123"
    record.trace_id = "0af7651916cd43dd8448eb211c80319c"
    record.span_id = "b7ad6b7169203331"
    record.http_method = "GET"
    record.http_path = "/test"
    record.http_status_code = 200
    record.duration_ms = 12.5
    record.streaming = True
    record.cancellation_reason = "client_disconnect"
    record.runtime_version = "0.28.0"
    record.environment = "production"
    record.provider_configured = True
    record.outcome = "completed"

    formatted = formatter.format(record)
    payload = json.loads(formatted)

    assert payload["level"] == "INFO"
    assert payload["logger"] == "trussium.test"
    assert payload["message"] == "Test message"
    assert payload["event"] == "test.event"
    assert payload["request_id"] == "request-123"
    assert payload["execution_id"] == "execution-123"
    assert payload["trace_id"] == "0af7651916cd43dd8448eb211c80319c"
    assert payload["span_id"] == "b7ad6b7169203331"
    assert payload["http_method"] == "GET"
    assert payload["http_path"] == "/test"
    assert payload["http_status_code"] == 200
    assert payload["duration_ms"] == 12.5
    assert payload["streaming"] is True
    assert payload["cancellation_reason"] == "client_disconnect"
    assert payload["runtime_version"] == "0.28.0"
    assert payload["environment"] == "production"
    assert payload["provider_configured"] is True
    assert payload["outcome"] == "completed"
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


def test_runtime_context_filter_enriches_log_record() -> None:
    """The filter should copy active execution fields to a log record."""
    context_token = set_request_id(
        "request-123",
        execution_id="execution-123",
    )

    try:
        with bind_execution_context(
            capability="chat.completions",
            provider="openai",
            model="gpt-5.6",
        ):
            record = logging.LogRecord(
                name="trussium.test",
                level=logging.INFO,
                pathname=__file__,
                lineno=1,
                msg="Test message",
                args=(),
                exc_info=None,
            )

            assert RuntimeContextFilter().filter(record) is True
            assert record.__dict__["request_id"] == "request-123"
            assert record.__dict__["execution_id"] == "execution-123"
            assert record.__dict__["capability"] == "chat.completions"
            assert record.__dict__["provider"] == "openai"
            assert record.__dict__["model"] == "gpt-5.6"
    finally:
        reset_request_id(context_token)


def test_runtime_context_filter_enriches_active_trace_context() -> None:
    """The filter should correlate records with the current sampled span."""
    exporter = InMemorySpanExporter()
    tracing = RuntimeTracing(
        ObservabilitySettings(tracing_enabled=True),
        span_processor=SimpleSpanProcessor(exporter),
    )

    with tracing.tracer.start_as_current_span("logging-test") as span:
        record = logging.LogRecord(
            name="trussium.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        assert RuntimeContextFilter().filter(record) is True
        assert record.__dict__["trace_id"] == f"{span.get_span_context().trace_id:032x}"
        assert record.__dict__["span_id"] == f"{span.get_span_context().span_id:016x}"

    tracing.shutdown()


def test_configured_logging_inherits_runtime_context() -> None:
    """Structured logs should automatically include active runtime context."""
    output = io.StringIO()
    configure_logging(
        stream=output,
    )
    context_token = set_request_id(
        "request-123",
        execution_id="execution-123",
    )

    try:
        with bind_execution_context(
            capability="chat.completions",
            provider="openai",
            model="gpt-5.6",
        ):
            get_logger("execution").info(
                "Capability execution started",
                extra={
                    "event": "capability.execution.started",
                },
            )
    finally:
        reset_request_id(context_token)

    payload = json.loads(output.getvalue())

    assert payload["request_id"] == "request-123"
    assert payload["execution_id"] == "execution-123"
    assert payload["capability"] == "chat.completions"
    assert payload["provider"] == "openai"
    assert payload["model"] == "gpt-5.6"


def test_explicit_log_fields_override_runtime_context() -> None:
    """Explicit structured fields should take precedence over inherited values."""
    output = io.StringIO()
    configure_logging(
        stream=output,
    )
    context_token = set_request_id(
        "context-request",
        execution_id="context-execution",
    )

    try:
        with bind_execution_context(
            capability="context-capability",
            provider="context-provider",
            model="context-model",
        ):
            get_logger("execution").info(
                "Explicit context",
                extra={
                    "request_id": "explicit-request",
                    "execution_id": "explicit-execution",
                    "capability": "explicit-capability",
                    "provider": "explicit-provider",
                    "model": "explicit-model",
                },
            )
    finally:
        reset_request_id(context_token)

    payload = json.loads(output.getvalue())

    assert payload["request_id"] == "explicit-request"
    assert payload["execution_id"] == "explicit-execution"
    assert payload["capability"] == "explicit-capability"
    assert payload["provider"] == "explicit-provider"
    assert payload["model"] == "explicit-model"


def test_logging_omits_inactive_runtime_context() -> None:
    """Empty context fields should not be serialized."""
    output = io.StringIO()
    configure_logging(
        stream=output,
    )

    get_logger("test").info("No active context")

    payload = json.loads(output.getvalue())

    assert "request_id" not in payload
    assert "execution_id" not in payload
    assert "capability" not in payload
    assert "provider" not in payload
    assert "model" not in payload


def test_get_logger_applies_trussium_namespace() -> None:
    """Component loggers should use the Trussium namespace."""
    logger = get_logger("http")

    assert logger.name == "trussium.http"
