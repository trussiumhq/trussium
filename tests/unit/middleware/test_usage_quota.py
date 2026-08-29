import asyncio

from starlette.types import Message, Receive, Scope, Send

from trussium.middleware.usage_quota import UsageQuotaMiddleware
from trussium.runtime import (
    ExecutionContext,
    UsageMeter,
    reset_execution_context,
    set_execution_context,
)


async def _ok_app(scope: Scope, receive: Receive, send: Send) -> None:
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


def test_usage_quota_rejects_after_request_budget() -> None:
    meter = UsageMeter(max_requests=1)
    middleware = UsageQuotaMiddleware(_ok_app, usage_meter=meter)
    token = set_execution_context(ExecutionContext(tenant_id="tenant-1"))
    try:
        meter.record()
        messages: list[Message] = []

        async def receive() -> Message:
            return {"type": "http.request"}

        async def send(message: Message) -> None:
            messages.append(message)

        asyncio.run(
            middleware(
                {"type": "http", "path": "/v1/chat/completions"},
                receive,
                send,
            )
        )
    finally:
        reset_execution_context(token)

    assert messages[0]["status"] == 429
    assert b"usage_quota_exceeded" in messages[1]["body"]


def test_usage_quota_passes_non_api_routes() -> None:
    middleware = UsageQuotaMiddleware(_ok_app, usage_meter=UsageMeter(max_requests=1))
    messages: list[Message] = []

    async def receive() -> Message:
        return {"type": "http.request"}

    async def send(message: Message) -> None:
        messages.append(message)

    asyncio.run(middleware({"type": "http", "path": "/health"}, receive, send))
    assert messages[0]["status"] == 200
