"""Opt-in bearer API-key authentication middleware."""

import hmac
import json

from pydantic import SecretStr
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send


class APIKeyAuthenticationMiddleware:
    """Require a configured bearer API key for application API routes."""

    _PUBLIC_PATHS = frozenset({"/health", "/ready", "/metrics", "/docs", "/redoc", "/openapi.json"})

    def __init__(self, app: ASGIApp, api_keys: tuple[SecretStr, ...]) -> None:
        self._app = app
        self._api_keys = tuple(key.get_secret_value() for key in api_keys)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or not self._api_keys
            or str(scope.get("path", "")) in self._PUBLIC_PATHS
            or not str(scope.get("path", "")).startswith("/v1/")
        ):
            await self._app(scope, receive, send)
            return

        authorization = Headers(scope=scope).get("authorization", "")
        scheme, _, credential = authorization.partition(" ")
        if scheme.lower() == "bearer" and credential and self._matches(credential):
            await self._app(scope, receive, send)
            return

        body = json.dumps(
            {
                "detail": {
                    "code": "authentication_required",
                    "message": "A valid API key is required.",
                }
            },
            separators=(",", ":"),
        ).encode()
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
            (b"www-authenticate", b"Bearer"),
        ]
        await send({"type": "http.response.start", "status": 401, "headers": headers})
        await send({"type": "http.response.body", "body": body})

    def _matches(self, credential: str) -> bool:
        return any(hmac.compare_digest(credential, key) for key in self._api_keys)
