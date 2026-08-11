"""Prometheus-compatible HTTP request instrumentation middleware."""

from asyncio import CancelledError
from time import perf_counter
from typing import Final

from starlette.requests import ClientDisconnect
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from trussium.observability import RuntimeMetrics

_EXCLUDED_PATHS: Final[frozenset[str]] = frozenset(
    {
        "/health/live",
        "/health/ready",
        "/metrics",
    }
)


class RequestMetricsMiddleware:
    """Measure full HTTP workload lifecycles with bounded labels."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        metrics: RuntimeMetrics,
    ) -> None:
        """Initialize the middleware."""
        self._app = app
        self._metrics = metrics

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        """Measure an ASGI HTTP workload request through termination."""
        if scope["type"] != "http" or str(scope.get("path", "")) in _EXCLUDED_PATHS:
            await self._app(scope, receive, send)
            return

        method = str(scope.get("method", "UNKNOWN")).upper() or "UNKNOWN"
        started_at = perf_counter()
        status_code: int | None = None
        response_complete = False
        client_disconnected = False
        outcome = "completed"

        self._metrics.request_started()

        async def send_with_status(message: Message) -> None:
            nonlocal response_complete, status_code

            if message["type"] == "http.response.start":
                response_status = message.get("status")

                if isinstance(response_status, int):
                    status_code = response_status

            await send(message)

            if message["type"] == "http.response.body" and not message.get("more_body", False):
                response_complete = True

        async def receive_with_disconnect() -> Message:
            nonlocal client_disconnected
            message = await receive()

            if message["type"] == "http.disconnect":
                client_disconnected = True

            return message

        try:
            await self._app(scope, receive_with_disconnect, send_with_status)
        except ClientDisconnect:
            outcome = "cancelled"
            raise
        except CancelledError:
            outcome = "cancelled"
            raise
        except Exception:
            outcome = "failed"
            raise
        else:
            if client_disconnected and not response_complete:
                outcome = "cancelled"
        finally:
            self._metrics.request_finished(
                method=method,
                outcome=outcome,
                status_code=self._terminal_status_code(status_code, outcome),
                duration_seconds=perf_counter() - started_at,
            )

    @staticmethod
    def _terminal_status_code(
        status_code: int | None,
        outcome: str,
    ) -> int:
        """Return a bounded terminal status for metric labels."""
        if status_code is not None:
            return status_code

        if outcome == "failed":
            return 500

        if outcome == "cancelled":
            return 499

        return 200
