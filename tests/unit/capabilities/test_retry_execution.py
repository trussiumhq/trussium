import asyncio

import pytest

from trussium.capabilities import CapabilityExecutionPipeline, CapabilityRegistry
from trussium.capabilities.errors import CapabilityErrorCategory, CapabilityExecutionError
from trussium.providers import RetryPolicy


def _pipeline(
    *, policy: RetryPolicy, timeout_seconds: float | None = None
) -> CapabilityExecutionPipeline:
    registry = CapabilityRegistry()
    registry.register("test.capability", object())
    registry.seal()
    return CapabilityExecutionPipeline(
        registry, retry_policy=policy, timeout_seconds=timeout_seconds
    )


def test_execute_retries_transient_failures_within_budget() -> None:
    calls = 0

    async def operation(_: object) -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise CapabilityExecutionError(
                code="upstream_connection",
                message="connection failed",
                category=CapabilityErrorCategory.UPSTREAM_CONNECTION,
            )
        return "ok"

    result = asyncio.run(
        _pipeline(policy=RetryPolicy(max_attempts=3, base_delay_seconds=0)).execute(
            "test.capability", operation
        )
    )
    assert result == "ok"
    assert calls == 3


def test_execute_applies_provider_timeout() -> None:
    async def operation(_: object) -> str:
        await asyncio.sleep(0.05)
        return "never"

    with pytest.raises(TimeoutError):
        asyncio.run(
            _pipeline(policy=RetryPolicy(max_attempts=1), timeout_seconds=0.001).execute(
                "test.capability", operation
            )
        )
