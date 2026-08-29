import asyncio

from pydantic import SecretStr
from starlette.types import Message, Receive, Scope, Send

from trussium.config.settings import APIKeyIdentity
from trussium.middleware.authentication import APIKeyAuthenticationMiddleware
from trussium.runtime import (
    ExecutionContext,
    get_execution_context,
    reset_execution_context,
    set_execution_context,
)


async def _app(scope: Scope, receive: Receive, send: Send) -> None:
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


async def _call(path: str, authorization: str | None = None) -> list[Message]:
    messages: list[Message] = []
    headers = [] if authorization is None else [(b"authorization", authorization.encode())]
    scope: Scope = {"type": "http", "path": path, "method": "GET", "headers": headers}

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        messages.append(message)

    await APIKeyAuthenticationMiddleware(_app, (SecretStr("secret-key"),))(scope, receive, send)
    return messages


async def _call_bound() -> tuple[list[Message], ExecutionContext]:
    messages: list[Message] = []
    observed: list[ExecutionContext] = []
    scope: Scope = {
        "type": "http",
        "path": "/v1/chat/completions",
        "method": "GET",
        "headers": [(b"authorization", b"Bearer bound-key")],
    }

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        messages.append(message)

    async def observed_app(scope: Scope, receive: Receive, send: Send) -> None:
        observed.append(get_execution_context())
        await _app(scope, receive, send)

    token = set_execution_context(ExecutionContext(tenant_id="untrusted"))
    try:
        await APIKeyAuthenticationMiddleware(
            observed_app,
            (),
            (
                APIKeyIdentity(
                    key=SecretStr("bound-key"),
                    tenant_id="tenant-1",
                    project_id="project-1",
                ),
            ),
        )(scope, receive, send)
        return messages, observed[0]
    finally:
        reset_execution_context(token)


def test_missing_key_is_rejected() -> None:
    messages = asyncio.run(_call("/v1/chat/completions"))
    assert messages[0]["status"] == 401
    assert (b"www-authenticate", b"Bearer") in messages[0]["headers"]


def test_valid_key_is_accepted() -> None:
    messages = asyncio.run(_call("/v1/chat/completions", "Bearer secret-key"))
    assert messages[0]["status"] == 200


def test_public_health_path_remains_available() -> None:
    messages = asyncio.run(_call("/health"))
    assert messages[0]["status"] == 200


def test_identity_binding_overrides_untrusted_context() -> None:
    messages, context = asyncio.run(_call_bound())
    assert messages[0]["status"] == 200
    assert context.tenant_id == "tenant-1"
    assert context.project_id == "project-1"


def test_identity_binding_denies_unlisted_capability() -> None:
    messages = asyncio.run(
        _call_with_binding(
            path="/v1/embeddings",
            capabilities=("chat",),
        )
    )
    assert messages[0]["status"] == 403


async def _call_with_binding(*, path: str, capabilities: tuple[str, ...]) -> list[Message]:
    messages: list[Message] = []
    scope: Scope = {
        "type": "http",
        "path": path,
        "method": "GET",
        "headers": [(b"authorization", b"Bearer bound-key")],
    }

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        messages.append(message)

    await APIKeyAuthenticationMiddleware(
        _app,
        (),
        (
            APIKeyIdentity(
                key=SecretStr("bound-key"),
                tenant_id="tenant-1",
                capabilities=capabilities,
            ),
        ),
    )(scope, receive, send)
    return messages
