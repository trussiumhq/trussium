"""Structured logging configuration."""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Final, TextIO

from trussium.runtime import get_execution_context

_TRUSSIUM_LOGGER_NAME: Final = "trussium"

_STRUCTURED_FIELDS: Final[tuple[str, ...]] = (
    "event",
    "request_id",
    "execution_id",
    "http_method",
    "http_path",
    "http_status_code",
    "duration_ms",
    "streaming",
    "cancellation_reason",
    "capability",
    "provider",
    "model",
    "error_code",
)


class RuntimeContextFilter(logging.Filter):
    """Attach active runtime context to structured log records."""

    def filter(
        self,
        record: logging.LogRecord,
    ) -> bool:
        """Enrich a log record with active execution context.

        Args:
            record: Log record to enrich.

        Returns:
            Always ``True`` so the record is emitted.
        """
        context = get_execution_context()

        context_fields: dict[str, str | None] = {
            "request_id": context.request_id,
            "execution_id": context.execution_id,
            "capability": context.capability,
            "provider": context.provider,
            "model": context.model,
        }

        for field_name, field_value in context_fields.items():
            if field_value is not None:
                record.__dict__.setdefault(
                    field_name,
                    field_value,
                )

        return True


class StructuredJsonFormatter(logging.Formatter):
    """Format log records as structured JSON."""

    def format(
        self,
        record: logging.LogRecord,
    ) -> str:
        """Format a log record.

        Args:
            record: Log record to format.

        Returns:
            JSON-formatted log entry.
        """
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(
                record.created,
                tz=UTC,
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for field_name in _STRUCTURED_FIELDS:
            field_value = getattr(
                record,
                field_name,
                None,
            )

            if field_value is not None:
                payload[field_name] = field_value

        if record.exc_info is not None:
            payload["exception"] = self.formatException(
                record.exc_info,
            )

        return json.dumps(
            payload,
            default=str,
            separators=(",", ":"),
        )


def configure_logging(
    *,
    debug: bool = False,
    stream: TextIO | None = None,
) -> None:
    """Configure the root Trussium logger.

    Args:
        debug: Enable debug-level Trussium logging.
        stream: Optional output stream override.
    """
    logger = logging.getLogger(_TRUSSIUM_LOGGER_NAME)

    logger.handlers.clear()

    handler = logging.StreamHandler(
        stream or sys.stdout,
    )
    handler.addFilter(
        RuntimeContextFilter(),
    )
    handler.setFormatter(
        StructuredJsonFormatter(),
    )

    logger.addHandler(handler)
    logger.setLevel(
        logging.DEBUG if debug else logging.INFO,
    )
    logger.propagate = False
    logger.disabled = False


def get_logger(
    name: str,
) -> logging.Logger:
    """Return a namespaced Trussium logger.

    Args:
        name: Logger component name.

    Returns:
        Namespaced logger.
    """
    if name == _TRUSSIUM_LOGGER_NAME:
        return logging.getLogger(name)

    if name.startswith(f"{_TRUSSIUM_LOGGER_NAME}."):
        return logging.getLogger(name)

    return logging.getLogger(
        f"{_TRUSSIUM_LOGGER_NAME}.{name}",
    )
