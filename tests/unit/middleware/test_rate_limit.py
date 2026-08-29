import asyncio

from starlette.types import Message, Receive, Scope, Send

from trussium.middleware.rate_limit import RateLimitMiddleware


async def _app(scope: Scope, receive: Receive, send: Send) -> None:
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


def test_rate_limit_returns_429_after_window_budget() -> None:
    async def scenario() -> list[Message]:
        middleware = RateLimitMiddleware(_app, max_requests=1, window_seconds=60.0)
        messages: list[Message] = []
        scope: Scope = {"type": "http", "path": "/v1/chat/completions", "method": "GET"}

        async def receive() -> Message:
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message: Message) -> None:
            messages.append(message)

        await middleware(scope, receive, send)
        await middleware(scope, receive, send)
        return messages

    messages = asyncio.run(scenario())
    assert [
        message["status"] for message in messages if message["type"] == "http.response.start"
    ] == [200, 429]
    retry_headers = dict(messages[-2]["headers"])
    assert 1 <= int(retry_headers[b"retry-after"]) <= 60


def test_disabled_rate_limit_passes_requests() -> None:
    async def scenario() -> list[Message]:
        middleware = RateLimitMiddleware(_app, max_requests=0, window_seconds=60.0)
        messages: list[Message] = []
        scope: Scope = {"type": "http", "path": "/v1/chat/completions", "method": "GET"}

        async def receive() -> Message:
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message: Message) -> None:
            messages.append(message)

        await middleware(scope, receive, send)
        return messages

    assert asyncio.run(scenario())[0]["status"] == 200
