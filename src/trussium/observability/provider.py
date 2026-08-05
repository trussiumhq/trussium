"""Structured provider execution logging."""

import logging
from collections.abc import AsyncIterator
from time import perf_counter
from typing import Final

from trussium.capabilities.chat import (
    ChatCapability,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatStreamErrorEvent,
    ChatStreamEvent,
)
from trussium.capabilities.errors import CapabilityExecutionError
from trussium.observability.logging import get_logger
from trussium.runtime import bind_execution_context

UNEXPECTED_PROVIDER_ERROR_CODE: Final = "provider_execution_failed"


class LoggingProviderChatCapability:
    """Decorate a provider chat adapter with structured lifecycle logging."""

    def __init__(
        self,
        capability: ChatCapability,
        *,
        provider: str,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize the provider logging decorator.

        Args:
            capability: Provider chat adapter to decorate.
            provider: Stable provider identifier.
            logger: Optional logger override.

        Raises:
            ValueError: When the provider identifier is empty.
        """
        normalized_provider = provider.strip()

        if not normalized_provider:
            raise ValueError("Provider name must not be empty")

        self._capability = capability
        self._provider = normalized_provider
        self._logger = logger or get_logger("provider")

    async def complete(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        """Execute a non-streaming provider request with lifecycle logging.

        Args:
            request: Provider-neutral chat-completion request.

        Returns:
            Normalized chat-completion response.

        Raises:
            CapabilityExecutionError: When provider execution fails.
            Exception: When the decorated provider raises unexpectedly.
        """
        with bind_execution_context(
            provider=self._provider,
            model=request.model,
        ):
            started_at = perf_counter()
            self._log_started(
                streaming=False,
            )

            try:
                response = await self._capability.complete(request)
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
        """Execute a streaming provider request with lifecycle logging.

        Args:
            request: Provider-neutral streaming chat request.

        Yields:
            Normalized chat streaming events from the decorated provider.

        Raises:
            CapabilityExecutionError: When provider execution fails.
            Exception: When the decorated provider raises unexpectedly.
        """
        with bind_execution_context(
            provider=self._provider,
            model=request.model,
        ):
            started_at = perf_counter()
            failed = False

            self._log_started(
                streaming=True,
            )

            try:
                async for event in self._capability.stream(request):
                    if isinstance(event, ChatStreamErrorEvent) and not failed:
                        self._log_failed(
                            started_at=started_at,
                            streaming=True,
                            error_code=event.code,
                        )
                        failed = True

                    yield event
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

    def _log_started(
        self,
        *,
        streaming: bool,
    ) -> None:
        """Emit a provider execution started event."""
        self._logger.info(
            "Provider execution started",
            extra={
                "event": "provider.execution.started",
                "streaming": streaming,
            },
        )

    def _log_completed(
        self,
        *,
        started_at: float,
        streaming: bool,
    ) -> None:
        """Emit a provider execution completed event."""
        self._logger.info(
            "Provider execution completed",
            extra={
                "event": "provider.execution.completed",
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
        """Emit a normalized provider execution failed event."""
        self._logger.error(
            "Provider execution failed",
            extra={
                "event": "provider.execution.failed",
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
        """Emit an unexpected provider execution failed event."""
        self._logger.exception(
            "Provider execution failed",
            extra={
                "event": "provider.execution.failed",
                "streaming": streaming,
                "duration_ms": self._duration_ms(started_at),
                "error_code": UNEXPECTED_PROVIDER_ERROR_CODE,
            },
        )

    @staticmethod
    def _duration_ms(
        started_at: float,
    ) -> float:
        """Return elapsed provider execution time in milliseconds."""
        return round(
            (perf_counter() - started_at) * 1000,
            3,
        )
