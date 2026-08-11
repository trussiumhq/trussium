"""OpenTelemetry HTTP request instrumentation middleware."""

from asyncio import CancelledError
from typing import Final

from opentelemetry.trace import Span, SpanKind, Status, StatusCode, Tracer
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from starlette.datastructures import Headers
from starlette.requests import ClientDisconnect
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from trussium.runtime import get_execution_context

_EXCLUDED_PATHS: Final[frozenset[str]] = frozenset(
    {
        "/health/live",
        "/health/ready",
        "/metrics",
    }
)


class RequestTracingMiddleware:
    """Trace complete HTTP request and streaming response lifecycles."""

    def __init__(self, app: ASGIApp, *, tracer: Tracer) -> None:
        """Initialize the middleware with an application-owned tracer."""
        self._app = app
        self._tracer = tracer
        self._propagator = TraceContextTextMapPropagator()

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        """Trace one HTTP request until its terminal response event."""
        path = str(scope.get("path", ""))

        if scope["type"] != "http" or path in _EXCLUDED_PATHS:
            await self._app(scope, receive, send)
            return

        method = str(scope.get("method", "UNKNOWN")).upper() or "UNKNOWN"
        parent_context = self._propagator.extract(
            carrier=dict(Headers(scope=scope).items()),
        )
        execution_context = get_execution_context()
        attributes: dict[str, str] = {
            "http.request.method": method,
            "trussium.outcome": "completed",
        }

        if execution_context.request_id is not None:
            attributes["trussium.request_id"] = execution_context.request_id

        if execution_context.execution_id is not None:
            attributes["trussium.execution_id"] = execution_context.execution_id

        with self._tracer.start_as_current_span(
            f"HTTP {method}",
            context=parent_context,
            kind=SpanKind.SERVER,
            attributes=attributes,
            record_exception=False,
            set_status_on_exception=False,
        ) as span:
            await self._trace_request(
                scope=scope,
                receive=receive,
                send=send,
                span=span,
            )

    async def _trace_request(
        self,
        *,
        scope: Scope,
        receive: Receive,
        send: Send,
        span: Span,
    ) -> None:
        """Run the downstream application while recording its outcome."""
        status_code: int | None = None
        response_complete = False
        client_disconnected = False

        async def send_with_status(message: Message) -> None:
            nonlocal client_disconnected, response_complete, status_code

            if message["type"] == "http.response.start":
                response_status = message.get("status")

                if isinstance(response_status, int):
                    status_code = response_status

            try:
                await send(message)
            except ClientDisconnect:
                client_disconnected = True
                raise

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
            self._mark_cancelled(span, "client_disconnect")
            raise
        except CancelledError:
            self._mark_cancelled(span, "task_cancelled")
            raise
        except Exception as error:
            span.set_attribute("trussium.outcome", "failed")
            span.set_attribute("error.type", type(error).__name__)
            span.set_status(Status(StatusCode.ERROR, type(error).__name__))
            raise
        else:
            if client_disconnected and not response_complete:
                self._mark_cancelled(span, "client_disconnect")

            if status_code is not None:
                span.set_attribute("http.response.status_code", status_code)

                if status_code >= 500:
                    span.set_status(Status(StatusCode.ERROR))

            route = scope.get("route")
            route_path = getattr(route, "path", None)

            if isinstance(route_path, str):
                span.set_attribute("http.route", route_path)

    @staticmethod
    def _mark_cancelled(span: Span, reason: str) -> None:
        """Record a bounded cancellation outcome."""
        span.set_attribute("trussium.outcome", "cancelled")
        span.set_attribute("trussium.cancellation_reason", reason)
        span.set_status(Status(StatusCode.ERROR, "cancelled"))
