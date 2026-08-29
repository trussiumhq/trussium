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
TENANT_ID_HEADER = "X-Tenant-ID"
PROJECT_ID_HEADER = "X-Project-ID"
APPLICATION_ID_HEADER = "X-Application-ID"


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
        tenant_id = self._resolve_tenant_id(scope)
        project_id = self._resolve_identity_id(scope, PROJECT_ID_HEADER)
        application_id = self._resolve_identity_id(scope, APPLICATION_ID_HEADER)
        context_token = set_request_id(
            request_id,
            tenant_id=tenant_id,
            project_id=project_id,
            application_id=application_id,
        )

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

    @staticmethod
    def _resolve_tenant_id(scope: Scope) -> str | None:
        """Resolve a bounded optional tenant identifier from request headers."""
        return RequestCorrelationMiddleware._resolve_identity_id(scope, TENANT_ID_HEADER)

    @staticmethod
    def _resolve_identity_id(scope: Scope, header_name: str) -> str | None:
        """Resolve a bounded optional identity identifier from request headers."""
        supplied_tenant_id = Headers(scope=scope).get(header_name)
        if supplied_tenant_id is None:
            return None
        normalized = supplied_tenant_id.strip()
        if not normalized or len(normalized) > 128:
            return None
        if any(not (character.isalnum() or character in "-_.:") for character in normalized):
            return None
        return normalized
