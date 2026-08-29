"""Bounded process-local request rate limiting middleware."""

import asyncio
import json
from collections import defaultdict, deque
from time import monotonic

from starlette.types import ASGIApp, Receive, Scope, Send

from trussium.runtime import get_execution_context


class RateLimitMiddleware:
    """Apply a fixed-window request limit to versioned API routes."""

    def __init__(self, app: ASGIApp, *, max_requests: int, window_seconds: float) -> None:
        self._app = app
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = str(scope.get("path", ""))
        if scope["type"] != "http" or self._max_requests <= 0 or not path.startswith("/v1/"):
            await self._app(scope, receive, send)
            return

        now = monotonic()
        key = self._bucket_key(scope)
        async with self._lock:
            bucket = self._requests[key]
            cutoff = now - self._window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self._max_requests:
                retry_after = max(1, int(bucket[0] + self._window_seconds - now))
                await self._send_error(send, retry_after=retry_after)
                return
            bucket.append(now)

        await self._app(scope, receive, send)

    @staticmethod
    def _bucket_key(scope: Scope) -> str:
        context = get_execution_context()
        identity = ":".join(
            value or "-"
            for value in (context.tenant_id, context.project_id, context.application_id)
        )
        if identity != "-:-:-":
            return f"identity:{identity}"
        client = scope.get("client")
        return f"client:{client[0]}" if isinstance(client, tuple) and client else "client:unknown"

    @staticmethod
    async def _send_error(send: Send, *, retry_after: int) -> None:
        body = json.dumps(
            {"detail": {"code": "rate_limit_exceeded", "message": "Rate limit exceeded."}},
            separators=(",", ":"),
        ).encode()
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
            (b"retry-after", str(retry_after).encode()),
        ]
        await send({"type": "http.response.start", "status": 429, "headers": headers})
        await send({"type": "http.response.body", "body": body})
