"""Structured HTTP request logging middleware."""

import logging
from time import perf_counter

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

        try:
            await self._app(
                scope,
                receive,
                send_with_status,
            )
        except Exception:
            duration_ms = round(
                (perf_counter() - started_at) * 1000,
                3,
            )

            self._logger.exception(
                "HTTP request failed",
                extra={
                    "event": "http.request.failed",
                    "request_id": request_id,
                    "http_method": method,
                    "http_path": path,
                    "http_status_code": (status_code if status_code is not None else 500),
                    "duration_ms": duration_ms,
                },
            )
            raise

        duration_ms = round(
            (perf_counter() - started_at) * 1000,
            3,
        )

        self._logger.info(
            "HTTP request completed",
            extra={
                "event": "http.request.completed",
                "request_id": request_id,
                "http_method": method,
                "http_path": path,
                "http_status_code": status_code,
                "duration_ms": duration_ms,
            },
        )
