"""Request-attribution audit middleware."""

from asyncio import CancelledError

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from trussium.runtime import AuditTrail


class AuditMiddleware:
    """Record bounded, payload-free audit events for versioned API requests."""

    def __init__(self, app: ASGIApp, *, audit_trail: AuditTrail) -> None:
        self._app = app
        self._audit_trail = audit_trail

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = str(scope.get("path", ""))
        if scope["type"] != "http" or not path.startswith("/v1/"):
            await self._app(scope, receive, send)
            return
        status_code: int | None = None

        async def send_with_status(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start" and isinstance(message.get("status"), int):
                status_code = message["status"]
            await send(message)

        method = str(scope.get("method", ""))
        try:
            await self._app(scope, receive, send_with_status)
        except CancelledError:
            self._audit_trail.record(
                method=method, path=path, status_code=status_code, outcome="cancelled"
            )
            raise
        except Exception:
            self._audit_trail.record(
                method=method, path=path, status_code=status_code or 500, outcome="failed"
            )
            raise
        self._audit_trail.record(
            method=method,
            path=path,
            status_code=status_code,
            outcome="success" if status_code is not None and status_code < 400 else "rejected",
        )
