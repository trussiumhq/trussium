"""Opt-in bearer API-key authentication middleware."""

import hmac
import json

from pydantic import SecretStr
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from trussium.config.settings import APIKeyIdentity
from trussium.runtime import (
    ExecutionContext,
    get_execution_context,
    reset_execution_context,
    set_execution_context,
)


class APIKeyAuthenticationMiddleware:
    """Require a configured bearer API key for application API routes."""

    _PUBLIC_PATHS = frozenset({"/health", "/ready", "/metrics", "/docs", "/redoc", "/openapi.json"})

    def __init__(
        self,
        app: ASGIApp,
        api_keys: tuple[SecretStr, ...],
        identity_bindings: tuple[APIKeyIdentity, ...] = (),
    ) -> None:
        self._app = app
        self._api_keys = tuple(key.get_secret_value() for key in api_keys)
        self._identity_bindings = tuple(
            (binding.key.get_secret_value(), binding) for binding in identity_bindings
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or not (self._api_keys or self._identity_bindings)
            or str(scope.get("path", "")) in self._PUBLIC_PATHS
            or not str(scope.get("path", "")).startswith("/v1/")
        ):
            await self._app(scope, receive, send)
            return

        authorization = Headers(scope=scope).get("authorization", "")
        scheme, _, credential = authorization.partition(" ")
        if scheme.lower() == "bearer" and credential:
            binding = self._matching_binding(credential)
            if binding is not None or self._matches(credential):
                context = get_execution_context()
                token = set_execution_context(
                    ExecutionContext(
                        request_id=context.request_id,
                        execution_id=context.execution_id,
                        capability=context.capability,
                        provider=context.provider,
                        model=context.model,
                        tenant_id=binding.tenant_id if binding is not None else None,
                        project_id=binding.project_id if binding is not None else None,
                        application_id=binding.application_id if binding is not None else None,
                    )
                )
                try:
                    await self._app(scope, receive, send)
                finally:
                    reset_execution_context(token)
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

    def _matching_binding(self, credential: str) -> APIKeyIdentity | None:
        for key, binding in self._identity_bindings:
            if hmac.compare_digest(credential, key):
                return binding
        return None
