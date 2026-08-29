"""Process-local identity-scoped usage quota middleware."""

import json

from starlette.types import ASGIApp, Receive, Scope, Send

from trussium.runtime import UsageMeter


class UsageQuotaMiddleware:
    """Reject versioned API requests that exceed the configured request quota."""

    def __init__(self, app: ASGIApp, *, usage_meter: UsageMeter) -> None:
        self._app = app
        self._usage_meter = usage_meter

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = str(scope.get("path", ""))
        if scope["type"] != "http" or not path.startswith("/v1/"):
            await self._app(scope, receive, send)
            return
        if not self._usage_meter.request_allowed():
            await self._send_error(send)
            return
        await self._app(scope, receive, send)

    @staticmethod
    async def _send_error(send: Send) -> None:
        body = json.dumps(
            {"detail": {"code": "usage_quota_exceeded", "message": "Usage quota exceeded."}},
            separators=(",", ":"),
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
