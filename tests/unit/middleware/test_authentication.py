import asyncio

from pydantic import SecretStr
from starlette.types import Message, Receive, Scope, Send

from trussium.middleware.authentication import APIKeyAuthenticationMiddleware


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
