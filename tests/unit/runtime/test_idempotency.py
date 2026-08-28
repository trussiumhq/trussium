import asyncio

import pytest

from trussium.runtime.idempotency import IdempotencyConflictError, IdempotencyStore


def test_idempotency_replays_success_and_rejects_conflicting_payload() -> None:
    store = IdempotencyStore()
    calls = 0

    async def operation() -> str:
        nonlocal calls
        calls += 1
        return "ok"

    async def run() -> None:
        assert await store.execute("key", {"value": 1}, operation) == "ok"
        assert await store.execute("key", {"value": 1}, operation) == "ok"
        with pytest.raises(IdempotencyConflictError):
            await store.execute("key", {"value": 2}, operation)

    asyncio.run(run())
    assert calls == 1


def test_idempotency_does_not_cache_failures() -> None:
    store = IdempotencyStore()
    calls = 0

    async def operation() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary")
        return "ok"

    async def run() -> str:
        with pytest.raises(RuntimeError):
            await store.execute("key", {}, operation)
        return await store.execute("key", {}, operation)

    assert asyncio.run(run()) == "ok"
    assert calls == 2
