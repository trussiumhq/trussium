"""Request-correlation middleware."""

from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import (
    ASGIApp,
    Message,
    Receive,
    Scope,
    Send,
)

from trussium.runtime import (
    reset_request_id,
    set_request_id,
)

REQUEST_ID_HEADER = "X-Request-ID"


class RequestCorrelationMiddleware:
    """Assign and propagate a correlation ID for HTTP requests."""

    def __init__(
        self,
        app: ASGIApp,
    ) -> None:
        """Initialize the middleware.

        Args:
            app: Wrapped ASGI application.
        """
        self._app = app

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

        request_id = self._resolve_request_id(scope)
        context_token = set_request_id(request_id)

        async def send_with_request_id(
            message: Message,
        ) -> None:
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                response_headers[REQUEST_ID_HEADER] = request_id

            await send(message)

        try:
            await self._app(
                scope,
                receive,
                send_with_request_id,
            )
        finally:
            reset_request_id(context_token)

    @staticmethod
    def _resolve_request_id(
        scope: Scope,
    ) -> str:
        """Resolve a supplied request ID or generate one.

        Args:
            scope: Current HTTP request scope.

        Returns:
            A supplied non-empty request identifier or a generated UUID.
        """
        headers = Headers(scope=scope)
        supplied_request_id = headers.get(REQUEST_ID_HEADER)

        if supplied_request_id is not None:
            normalized_request_id = supplied_request_id.strip()

            if normalized_request_id:
                return normalized_request_id

        return str(uuid4())
