"""Structured capability execution logging."""

import logging
from asyncio import CancelledError
from collections.abc import AsyncIterator
from time import perf_counter
from typing import Final

from opentelemetry import trace
from opentelemetry.trace import NoOpTracerProvider, SpanKind, Status, StatusCode, Tracer

from trussium.capabilities.chat import (
    CHAT_CAPABILITY_NAME,
    ChatCapability,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatStreamErrorEvent,
    ChatStreamEvent,
)
from trussium.capabilities.errors import CapabilityExecutionError
from trussium.observability.logging import get_logger
from trussium.runtime import bind_execution_context
from trussium.runtime.streaming import close_async_resource

UNEXPECTED_CAPABILITY_ERROR_CODE: Final = "capability_execution_failed"


class LoggingChatCapability:
    """Decorate a chat capability with structured lifecycle logging."""

    def __init__(
        self,
        capability: ChatCapability,
        logger: logging.Logger | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        """Initialize the logging decorator.

        Args:
            capability: Provider-neutral chat capability to decorate.
            logger: Optional logger override.
            tracer: Optional application-owned OpenTelemetry tracer.
        """
        self._capability = capability
        self._logger = logger or get_logger("capability")
        self._tracer = tracer or NoOpTracerProvider().get_tracer(
            "trussium.capability",
        )

    async def complete(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        """Execute a non-streaming chat completion with lifecycle logging.

        Args:
            request: Provider-neutral chat-completion request.

        Returns:
            Normalized chat-completion response.

        Raises:
            CapabilityExecutionError: When capability execution fails.
            Exception: When the decorated capability raises unexpectedly.
        """
        with (
            bind_execution_context(
                capability=CHAT_CAPABILITY_NAME,
                model=request.model,
            ),
            self._tracer.start_as_current_span(
                "trussium.capability.chat",
                kind=SpanKind.INTERNAL,
                attributes={
                    "gen_ai.operation.name": "chat",
                    "gen_ai.request.model": request.model,
                    "trussium.capability": CHAT_CAPABILITY_NAME,
                    "trussium.streaming": False,
                },
                record_exception=False,
                set_status_on_exception=False,
            ),
        ):
            started_at = perf_counter()
            self._log_started(
                streaming=False,
            )

            try:
                response = await self._capability.complete(request)
            except CancelledError:
                self._log_cancelled(
                    started_at=started_at,
                    streaming=False,
                )
                raise
            except CapabilityExecutionError as error:
                self._log_failed(
                    started_at=started_at,
                    streaming=False,
                    error_code=error.code,
                )
                raise
            except Exception:
                self._log_unexpected_failure(
                    started_at=started_at,
                    streaming=False,
                )
                raise

            self._log_completed(
                started_at=started_at,
                streaming=False,
            )

            return response

    async def stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[ChatStreamEvent]:
        """Execute a streaming chat completion with lifecycle logging.

        Args:
            request: Provider-neutral streaming chat request.

        Yields:
            Normalized chat streaming events from the decorated capability.

        Raises:
            CapabilityExecutionError: When capability execution fails.
            Exception: When the decorated capability raises unexpectedly.
        """
        with (
            bind_execution_context(
                capability=CHAT_CAPABILITY_NAME,
                model=request.model,
            ),
            self._tracer.start_as_current_span(
                "trussium.capability.chat",
                kind=SpanKind.INTERNAL,
                attributes={
                    "gen_ai.operation.name": "chat",
                    "gen_ai.request.model": request.model,
                    "trussium.capability": CHAT_CAPABILITY_NAME,
                    "trussium.streaming": True,
                },
                record_exception=False,
                set_status_on_exception=False,
            ),
        ):
            started_at = perf_counter()
            failed = False

            self._log_started(
                streaming=True,
            )

            events = self._capability.stream(request)

            try:
                async for event in events:
                    if isinstance(event, ChatStreamErrorEvent) and not failed:
                        self._log_failed(
                            started_at=started_at,
                            streaming=True,
                            error_code=event.code,
                        )
                        failed = True

                    yield event
            except (CancelledError, GeneratorExit):
                await close_async_resource(events)

                if not failed:
                    self._log_cancelled(
                        started_at=started_at,
                        streaming=True,
                    )
                raise
            except CapabilityExecutionError as error:
                if not failed:
                    self._log_failed(
                        started_at=started_at,
                        streaming=True,
                        error_code=error.code,
                    )
                raise
            except Exception:
                if not failed:
                    self._log_unexpected_failure(
                        started_at=started_at,
                        streaming=True,
                    )
                raise

            if not failed:
                self._log_completed(
                    started_at=started_at,
                    streaming=True,
                )

    def _log_cancelled(
        self,
        *,
        started_at: float,
        streaming: bool,
    ) -> None:
        """Emit a capability execution cancelled event."""
        self._set_span_outcome(
            outcome="cancelled",
            error_code="task_cancelled",
        )
        self._logger.info(
            "Capability execution cancelled",
            extra={
                "event": "capability.execution.cancelled",
                "streaming": streaming,
                "duration_ms": self._duration_ms(started_at),
                "cancellation_reason": "task_cancelled",
            },
        )

    def _log_started(
        self,
        *,
        streaming: bool,
    ) -> None:
        """Emit a capability execution started event."""
        self._logger.info(
            "Capability execution started",
            extra={
                "event": "capability.execution.started",
                "streaming": streaming,
            },
        )

    def _log_completed(
        self,
        *,
        started_at: float,
        streaming: bool,
    ) -> None:
        """Emit a capability execution completed event."""
        self._set_span_outcome(outcome="completed")
        self._logger.info(
            "Capability execution completed",
            extra={
                "event": "capability.execution.completed",
                "streaming": streaming,
                "duration_ms": self._duration_ms(started_at),
            },
        )

    def _log_failed(
        self,
        *,
        started_at: float,
        streaming: bool,
        error_code: str,
    ) -> None:
        """Emit a normalized capability execution failed event."""
        self._set_span_outcome(
            outcome="failed",
            error_code=error_code,
        )
        self._logger.error(
            "Capability execution failed",
            extra={
                "event": "capability.execution.failed",
                "streaming": streaming,
                "duration_ms": self._duration_ms(started_at),
                "error_code": error_code,
            },
        )

    def _log_unexpected_failure(
        self,
        *,
        started_at: float,
        streaming: bool,
    ) -> None:
        """Emit an unexpected capability execution failed event."""
        self._set_span_outcome(
            outcome="failed",
            error_code=UNEXPECTED_CAPABILITY_ERROR_CODE,
        )
        self._logger.exception(
            "Capability execution failed",
            extra={
                "event": "capability.execution.failed",
                "streaming": streaming,
                "duration_ms": self._duration_ms(started_at),
                "error_code": UNEXPECTED_CAPABILITY_ERROR_CODE,
            },
        )

    @staticmethod
    def _duration_ms(
        started_at: float,
    ) -> float:
        """Return elapsed execution time in milliseconds."""
        return round(
            (perf_counter() - started_at) * 1000,
            3,
        )

    @staticmethod
    def _set_span_outcome(
        *,
        outcome: str,
        error_code: str | None = None,
    ) -> None:
        """Attach a bounded terminal outcome to the active span."""
        span = trace.get_current_span()
        span.set_attribute("trussium.outcome", outcome)

        if error_code is not None:
            span.set_attribute("error.type", error_code)
            span.set_status(Status(StatusCode.ERROR, error_code))
