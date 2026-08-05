"""Structured HTTP request logging middleware."""

import logging
from asyncio import CancelledError
from time import perf_counter

from starlette.requests import ClientDisconnect
from starlette.types import (
    ASGIApp,
    Message,
    Receive,
    Scope,
    Send,
)

from trussium.observability import get_logger
from trussium.runtime import get_request_id


class RequestLoggingMiddleware:
    """Emit structured logs for the HTTP request lifecycle."""

    def __init__(
        self,
        app: ASGIApp,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize the middleware.

        Args:
            app: Wrapped ASGI application.
            logger: Optional logger override.
        """
        self._app = app
        self._logger = logger or get_logger("http")

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        """Process an ASGI connection.

        Args:
            scope: ASGI connection scope.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request_id = get_request_id()
        method = str(scope.get("method", ""))
        path = str(scope.get("path", ""))
        started_at = perf_counter()
        status_code: int | None = None
        client_disconnected = False

        self._logger.info(
            "HTTP request started",
            extra={
                "event": "http.request.started",
                "request_id": request_id,
                "http_method": method,
                "http_path": path,
            },
        )

        async def send_with_status(
            message: Message,
        ) -> None:
            nonlocal status_code

            if message["type"] == "http.response.start":
                response_status = message.get("status")

                if isinstance(response_status, int):
                    status_code = response_status

            await send(message)

        async def receive_with_disconnect() -> Message:
            nonlocal client_disconnected

            message = await receive()

            if message["type"] == "http.disconnect":
                client_disconnected = True

            return message

        try:
            await self._app(
                scope,
                receive_with_disconnect,
                send_with_status,
            )
        except ClientDisconnect:
            self._log_cancelled(
                request_id=request_id,
                method=method,
                path=path,
                status_code=status_code,
                started_at=started_at,
                cancellation_reason="client_disconnect",
            )
            return
        except CancelledError:
            self._log_cancelled(
                request_id=request_id,
                method=method,
                path=path,
                status_code=status_code,
                started_at=started_at,
                cancellation_reason="task_cancelled",
            )
            raise
        except Exception:
            self._logger.exception(
                "HTTP request failed",
                extra={
                    "event": "http.request.failed",
                    "request_id": request_id,
                    "http_method": method,
                    "http_path": path,
                    "http_status_code": (status_code if status_code is not None else 500),
                    "duration_ms": self._duration_ms(started_at),
                },
            )
            raise

        if client_disconnected:
            self._log_cancelled(
                request_id=request_id,
                method=method,
                path=path,
                status_code=status_code,
                started_at=started_at,
                cancellation_reason="client_disconnect",
            )
            return

        self._logger.info(
            "HTTP request completed",
            extra={
                "event": "http.request.completed",
                "request_id": request_id,
                "http_method": method,
                "http_path": path,
                "http_status_code": status_code,
                "duration_ms": self._duration_ms(started_at),
            },
        )

    def _log_cancelled(
        self,
        *,
        request_id: str | None,
        method: str,
        path: str,
        status_code: int | None,
        started_at: float,
        cancellation_reason: str,
    ) -> None:
        """Emit a structured HTTP request cancellation event."""
        self._logger.info(
            "HTTP request cancelled",
            extra={
                "event": "http.request.cancelled",
                "request_id": request_id,
                "http_method": method,
                "http_path": path,
                "http_status_code": status_code,
                "duration_ms": self._duration_ms(started_at),
                "cancellation_reason": cancellation_reason,
            },
        )

    @staticmethod
    def _duration_ms(
        started_at: float,
    ) -> float:
        """Return elapsed request time in milliseconds."""
        return round(
            (perf_counter() - started_at) * 1000,
            3,
        )
