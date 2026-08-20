"""Tests for deterministic capability health reporting."""

import asyncio
import io
import json
from math import inf, nan
from typing import cast

import pytest

from trussium.capabilities import (
    CAPABILITY_HEALTH_CHECK_FAILED,
    CAPABILITY_HEALTH_NOT_REPORTED,
    CAPABILITY_HEALTH_TIMEOUT,
    CapabilityHealth,
    CapabilityHealthReporter,
    CapabilityHealthStatus,
    CapabilityRegistry,
)
from trussium.observability import configure_logging


class HealthCapability:
    """Capability returning a configured health value or failure."""

    def __init__(
        self, name: str, result: CapabilityHealth | BaseException | object, *, delay: float = 0
    ) -> None:
        self.name = name
        self.result = result
        self.delay = delay
        self.calls = 0

    async def check_health(self) -> CapabilityHealth:
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if isinstance(self.result, BaseException):
            raise self.result
        return cast(CapabilityHealth, self.result)


def sealed_registry(*registrations: tuple[str, object]) -> CapabilityRegistry:
    """Return a registry sealed with the supplied ordered registrations."""
    registry = CapabilityRegistry()
    for name, capability in registrations:
        registry.register(name, capability)
    registry.seal()
    return registry


def test_values_enforce_bounded_semantics() -> None:
    """Capability health values should reject unsafe identities and reasons."""
    assert CapabilityHealth("chat.completions", CapabilityHealthStatus.OK).reason is None
    with pytest.raises(ValueError, match="must not include"):
        CapabilityHealth("chat.completions", CapabilityHealthStatus.OK, "unexpected")
    with pytest.raises(ValueError, match="reasons must match"):
        CapabilityHealth("chat.completions", CapabilityHealthStatus.DEGRADED)
    with pytest.raises(ValueError, match="CapabilityHealthStatus"):
        CapabilityHealth("chat.completions", cast(CapabilityHealthStatus, "ok"))


@pytest.mark.parametrize("timeout", [0.0, -1.0, inf, nan])
def test_reporter_requires_sealed_registry_and_positive_deadline(timeout: float) -> None:
    """Reporter ownership and deadlines should fail before evaluation."""
    with pytest.raises(ValueError, match="sealed registry"):
        CapabilityHealthReporter(CapabilityRegistry())
    with pytest.raises(ValueError, match="finite and positive"):
        CapabilityHealthReporter(sealed_registry(), timeout_seconds=timeout)


def test_empty_and_unreported_registries_have_safe_states() -> None:
    """Empty reports are ok while ordinary registrations remain unknown."""
    assert (
        asyncio.run(CapabilityHealthReporter(sealed_registry()).report()).status
        is CapabilityHealthStatus.OK
    )
    report = asyncio.run(CapabilityHealthReporter(sealed_registry(("images", object()))).report())
    assert report.status is CapabilityHealthStatus.UNKNOWN
    assert report.capabilities == (
        CapabilityHealth("images", CapabilityHealthStatus.UNKNOWN, CAPABILITY_HEALTH_NOT_REPORTED),
    )


def test_order_precedence_and_owned_failures_are_deterministic() -> None:
    """Checks preserve registry order and normalize owned failure boundaries."""
    healthy = HealthCapability("healthy", CapabilityHealth("healthy", CapabilityHealthStatus.OK))
    degraded = HealthCapability(
        "degraded", CapabilityHealth("degraded", CapabilityHealthStatus.DEGRADED, "warming")
    )
    timed_out = HealthCapability(
        "timeout", CapabilityHealth("timeout", CapabilityHealthStatus.OK), delay=1
    )
    failed = HealthCapability("failed", RuntimeError("secret endpoint"))
    mismatched = HealthCapability("expected", CapabilityHealth("other", CapabilityHealthStatus.OK))
    report = asyncio.run(
        CapabilityHealthReporter(
            sealed_registry(
                ("healthy", healthy),
                ("ordinary", object()),
                ("degraded", degraded),
                ("timeout", timed_out),
                ("failed", failed),
                ("expected", mismatched),
            ),
            timeout_seconds=0.001,
        ).report()
    )
    assert report.status is CapabilityHealthStatus.UNAVAILABLE
    assert [(item.name, item.reason) for item in report.capabilities] == [
        ("healthy", None),
        ("ordinary", CAPABILITY_HEALTH_NOT_REPORTED),
        ("degraded", "warming"),
        ("timeout", CAPABILITY_HEALTH_TIMEOUT),
        ("failed", CAPABILITY_HEALTH_CHECK_FAILED),
        ("expected", CAPABILITY_HEALTH_CHECK_FAILED),
    ]


def test_checks_are_concurrent_serialized_and_cancellation_safe() -> None:
    """Reports should run one concurrent batch and preserve cancellation identity."""
    both_started = asyncio.Event()
    started = 0

    class ConcurrentCapability:
        def __init__(self, name: str) -> None:
            self.name = name

        async def check_health(self) -> CapabilityHealth:
            nonlocal started
            started += 1
            if started == 2:
                both_started.set()
            await both_started.wait()
            return CapabilityHealth(self.name, CapabilityHealthStatus.OK)

    first = ConcurrentCapability("first")
    second = ConcurrentCapability("second")
    report = asyncio.run(
        CapabilityHealthReporter(sealed_registry(("first", first), ("second", second))).report()
    )
    assert [item.name for item in report.capabilities] == ["first", "second"]

    cancelled = HealthCapability("cancelled", asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(CapabilityHealthReporter(sealed_registry(("cancelled", cancelled))).report())


def test_transition_logs_are_bounded_and_not_repeated() -> None:
    """Repeated states should emit once without raw failure information."""
    output = io.StringIO()
    configure_logging(stream=output)
    capability = HealthCapability("chat", RuntimeError("secret at private endpoint"))
    reporter = CapabilityHealthReporter(sealed_registry(("chat", capability)))

    async def exercise() -> None:
        await reporter.report()
        await reporter.report()
        capability.result = CapabilityHealth("chat", CapabilityHealthStatus.OK)
        await reporter.report()

    asyncio.run(exercise())
    payloads = [json.loads(line) for line in output.getvalue().splitlines()]
    assert [payload["event"] for payload in payloads] == [
        "capability.health.unavailable",
        "capability.health.ok",
    ]
    assert payloads[0]["error_code"] == CAPABILITY_HEALTH_CHECK_FAILED
    assert "secret" not in output.getvalue()
