"""Tests for structured request logging."""

import logging
from typing import cast


class StructuredLogRecord(logging.LogRecord):
    """Log record containing Trussium structured fields."""

    event: str
    request_id: str | None
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
