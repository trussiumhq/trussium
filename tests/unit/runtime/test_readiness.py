"""Tests for bounded dependency readiness evaluation."""

import asyncio
import io
import json
from collections.abc import Callable

import pytest

from trussium.observability import configure_logging
from trussium.runtime import (
    DependencyFailureReason,
    DependencyHealth,
    DependencyReadiness,
    DependencyStatus,
)


class StubHealthCheck:
    """Controllable dependency check used by evaluator tests."""

    name = "provider"
    provider = "openai"
    model = "private-model-name"

    def __init__(
        self,
        result: DependencyHealth | None = None,
        *,
        delay: float = 0.0,
        error: BaseException | None = None,
    ) -> None:
        """Initialize the controllable result."""
        self.result = result or DependencyHealth(
            name=self.name,
            status=DependencyStatus.OK,
            provider=self.provider,
            model=self.model,
        )
        self.delay = delay
        self.error = error
        self.calls = 0
        self.closed = False

    async def check(self) -> DependencyHealth:
        """Return or raise the configured result."""
        self.calls += 1

        if self.delay:
            await asyncio.sleep(self.delay)

        if self.error is not None:
            raise self.error

        return self.result

    async def close(self) -> None:
        """Record resource closure."""
        self.closed = True


def mutable_clock() -> tuple[Callable[[], float], Callable[[float], None]]:
    """Return a deterministic monotonic clock and advancement function."""
    current = 0.0

    def clock() -> float:
        return current

    def advance(seconds: float) -> None:
        nonlocal current
        current += seconds

    return clock, advance


def test_readiness_reuses_results_until_monotonic_cache_expires() -> None:
    """Cached checks should refresh only after their monotonic TTL."""
    check = StubHealthCheck()
    clock, advance = mutable_clock()
    readiness = DependencyReadiness(
        check,
        timeout_seconds=1.0,
        cache_seconds=10.0,
        clock=clock,
    )

    async def exercise() -> None:
        first = await readiness.evaluate()
        advance(9.9)
        cached = await readiness.evaluate()
        advance(0.1)
        refreshed = await readiness.evaluate()

        assert first is cached
        assert refreshed is check.result

    asyncio.run(exercise())
    assert check.calls == 2


def test_concurrent_stale_probes_share_one_refresh() -> None:
    """Concurrent probes should not fan out provider metadata requests."""
    check = StubHealthCheck(delay=0.02)
    readiness = DependencyReadiness(
        check,
        timeout_seconds=1.0,
        cache_seconds=10.0,
    )

    async def exercise() -> list[DependencyHealth]:
        return await asyncio.gather(*(readiness.evaluate() for _ in range(12)))

    results = asyncio.run(exercise())

    assert check.calls == 1
    assert results == [check.result] * 12


def test_runtime_deadline_normalizes_slow_provider_without_raw_failure() -> None:
    """Runtime timeout ownership should produce one stable bounded reason."""
    check = StubHealthCheck(delay=0.05)
    readiness = DependencyReadiness(
        check,
        timeout_seconds=0.001,
        cache_seconds=10.0,
    )

    result = asyncio.run(readiness.evaluate())

    assert result == DependencyHealth(
        name="provider",
        status=DependencyStatus.UNAVAILABLE,
        provider="openai",
        model="private-model-name",
        reason=DependencyFailureReason.PROVIDER_TIMEOUT,
    )


def test_unexpected_provider_failure_is_bounded_and_caller_cancellation_propagates() -> None:
    """Unexpected failures should normalize without masking caller cancellation."""
    failed = DependencyReadiness(
        StubHealthCheck(error=RuntimeError("private endpoint and credential")),
        timeout_seconds=1.0,
        cache_seconds=10.0,
    )
    result = asyncio.run(failed.evaluate())

    assert result.reason is DependencyFailureReason.PROVIDER_CHECK_FAILED

    cancelled = DependencyReadiness(
        StubHealthCheck(error=asyncio.CancelledError()),
        timeout_seconds=1.0,
        cache_seconds=10.0,
    )

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(cancelled.evaluate())


def test_state_transition_logs_are_bounded_and_resources_close() -> None:
    """Only transitions should log and raw provider failures must remain absent."""
    output = io.StringIO()
    configure_logging(stream=output)
    check = StubHealthCheck()
    clock, advance = mutable_clock()
    readiness = DependencyReadiness(
        check,
        timeout_seconds=1.0,
        cache_seconds=1.0,
        clock=clock,
    )

    async def exercise() -> None:
        await readiness.evaluate()
        advance(1.0)
        await readiness.evaluate()
        check.result = DependencyHealth(
            name="provider",
            status=DependencyStatus.UNAVAILABLE,
            provider="openai",
            model="private-model-name",
            reason=DependencyFailureReason.PROVIDER_AUTHENTICATION_FAILED,
        )
        advance(1.0)
        await readiness.evaluate()
        await readiness.close()

    asyncio.run(exercise())
    events = [json.loads(line) for line in output.getvalue().splitlines()]

    assert [event["event"] for event in events] == [
        "readiness.dependency.ok",
        "readiness.dependency.unavailable",
    ]
    assert events[1]["error_code"] == "provider_authentication_failed"
    assert "endpoint" not in output.getvalue().lower()
    assert "credential" not in output.getvalue().lower()
    assert check.closed is True
