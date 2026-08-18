"""Tests for deterministic runtime component health reporting."""

import asyncio
import io
import json
from math import inf, nan
from typing import cast

import pytest

from trussium.observability import configure_logging
from trussium.runtime import (
    COMPONENT_HEALTH_CHECK_FAILED,
    COMPONENT_HEALTH_NOT_REPORTED,
    COMPONENT_HEALTH_TIMEOUT,
    RuntimeComponentHealth,
    RuntimeComponentHealthReporter,
    RuntimeComponentStatus,
    RuntimeServiceRegistry,
)


class StubRuntimeService:
    """Runtime service without the optional health-reporting protocol."""

    def __init__(self, name: str) -> None:
        """Store the stable service name."""
        self.name = name

    async def startup(self) -> None:
        """Implement the lifecycle startup contract."""

    async def shutdown(self) -> None:
        """Implement the lifecycle shutdown contract."""


class HealthRuntimeService(StubRuntimeService):
    """Runtime service returning a configured health result or failure."""

    def __init__(
        self,
        name: str,
        result: RuntimeComponentHealth | BaseException | object,
        *,
        delay: float = 0.0,
    ) -> None:
        """Configure the health check result and optional delay."""
        super().__init__(name)
        self.result = result
        self.delay = delay
        self.calls = 0

    async def check_health(self) -> RuntimeComponentHealth:
        """Return or raise the configured result."""
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if isinstance(self.result, BaseException):
            raise self.result
        return cast(RuntimeComponentHealth, self.result)


def sealed_registry(*services: StubRuntimeService) -> RuntimeServiceRegistry:
    """Return a registry sealed with the supplied services."""
    registry = RuntimeServiceRegistry(services)
    registry.seal()
    return registry


def test_component_health_values_enforce_bounded_semantics() -> None:
    """Component values should reject unsafe identities and reason states."""
    assert RuntimeComponentHealth(
        name="cache",
        status=RuntimeComponentStatus.OK,
    ) == RuntimeComponentHealth(name="cache", status=RuntimeComponentStatus.OK)

    with pytest.raises(ValueError, match="must match"):
        RuntimeComponentHealth(name="UPPER", status=RuntimeComponentStatus.OK)
    with pytest.raises(ValueError, match="must not include"):
        RuntimeComponentHealth(
            name="cache",
            status=RuntimeComponentStatus.OK,
            reason="unexpected_reason",
        )
    with pytest.raises(ValueError, match="reasons must match"):
        RuntimeComponentHealth(name="cache", status=RuntimeComponentStatus.DEGRADED)
    with pytest.raises(ValueError, match="reasons must match"):
        RuntimeComponentHealth(
            name="cache",
            status=RuntimeComponentStatus.UNAVAILABLE,
            reason="private detail",
        )
    with pytest.raises(ValueError, match="RuntimeComponentStatus"):
        RuntimeComponentHealth(
            name="cache",
            status=cast(RuntimeComponentStatus, "ok"),
        )


@pytest.mark.parametrize("timeout", [0.0, -1.0, inf, nan])
def test_reporter_requires_sealed_registry_and_positive_deadline(timeout: float) -> None:
    """Reporting ownership and deadlines should fail before evaluation."""
    with pytest.raises(ValueError, match="sealed registry"):
        RuntimeComponentHealthReporter(RuntimeServiceRegistry())

    with pytest.raises(ValueError, match="finite and positive"):
        RuntimeComponentHealthReporter(sealed_registry(), timeout_seconds=timeout)


def test_empty_registry_reports_ok() -> None:
    """No registered components should produce a healthy empty aggregate."""
    registry = sealed_registry()
    reporter = RuntimeComponentHealthReporter(registry, timeout_seconds=0.5)

    report = asyncio.run(reporter.report())

    assert reporter.registry is registry
    assert reporter.timeout_seconds == 0.5
    assert report.status is RuntimeComponentStatus.OK
    assert report.components == ()


def test_unreported_component_produces_unknown_aggregate() -> None:
    """A registry with only non-reporting services should aggregate unknown."""
    report = asyncio.run(
        RuntimeComponentHealthReporter(sealed_registry(StubRuntimeService("cache"))).report()
    )

    assert report.status is RuntimeComponentStatus.UNKNOWN
    assert report.components == (
        RuntimeComponentHealth(
            name="cache",
            status=RuntimeComponentStatus.UNKNOWN,
            reason=COMPONENT_HEALTH_NOT_REPORTED,
        ),
    )


def test_report_uses_registered_identity_snapshot() -> None:
    """Later service attribute mutation must not change registry-owned identity."""
    service = StubRuntimeService("stable")
    registry = sealed_registry(service)
    service.name = "changed"

    report = asyncio.run(RuntimeComponentHealthReporter(registry).report())

    assert report.components[0].name == "stable"


def test_registered_order_and_aggregate_precedence_are_deterministic() -> None:
    """Completion timing must not alter ordered output or aggregate severity."""
    healthy = HealthRuntimeService(
        "healthy",
        RuntimeComponentHealth(name="healthy", status=RuntimeComponentStatus.OK),
        delay=0.02,
    )
    unreported = StubRuntimeService("unreported")
    degraded = HealthRuntimeService(
        "degraded",
        RuntimeComponentHealth(
            name="degraded",
            status=RuntimeComponentStatus.DEGRADED,
            reason="cache_warming",
        ),
    )
    unavailable = HealthRuntimeService(
        "unavailable",
        RuntimeComponentHealth(
            name="unavailable",
            status=RuntimeComponentStatus.UNAVAILABLE,
            reason="connection_lost",
        ),
        delay=0.01,
    )
    reporter = RuntimeComponentHealthReporter(
        sealed_registry(healthy, unreported, degraded, unavailable),
        timeout_seconds=0.5,
    )

    report = asyncio.run(reporter.report())

    assert report.status is RuntimeComponentStatus.UNAVAILABLE
    assert report.components == (
        RuntimeComponentHealth(name="healthy", status=RuntimeComponentStatus.OK),
        RuntimeComponentHealth(
            name="unreported",
            status=RuntimeComponentStatus.UNKNOWN,
            reason=COMPONENT_HEALTH_NOT_REPORTED,
        ),
        RuntimeComponentHealth(
            name="degraded",
            status=RuntimeComponentStatus.DEGRADED,
            reason="cache_warming",
        ),
        RuntimeComponentHealth(
            name="unavailable",
            status=RuntimeComponentStatus.UNAVAILABLE,
            reason="connection_lost",
        ),
    )


def test_checks_execute_concurrently() -> None:
    """Independent component deadlines should not accumulate sequentially."""
    both_started = asyncio.Event()
    started = 0

    class ConcurrentHealthService(StubRuntimeService):
        async def check_health(self) -> RuntimeComponentHealth:
            nonlocal started
            started += 1
            if started == 2:
                both_started.set()
            await both_started.wait()
            return RuntimeComponentHealth(name=self.name, status=RuntimeComponentStatus.OK)

    reporter = RuntimeComponentHealthReporter(
        sealed_registry(ConcurrentHealthService("first"), ConcurrentHealthService("second")),
        timeout_seconds=0.1,
    )

    report = asyncio.run(reporter.report())

    assert report.status is RuntimeComponentStatus.OK
    assert [component.name for component in report.components] == ["first", "second"]


def test_timeout_exception_invalid_and_mismatched_results_are_normalized() -> None:
    """Owned failure boundaries should return stable safe component states."""
    timeout = HealthRuntimeService(
        "timeout",
        RuntimeComponentHealth(name="timeout", status=RuntimeComponentStatus.OK),
        delay=1.0,
    )
    failed = HealthRuntimeService("failed", RuntimeError("credential at private endpoint"))
    invalid = HealthRuntimeService("invalid", object())
    mismatched = HealthRuntimeService(
        "expected",
        RuntimeComponentHealth(name="other", status=RuntimeComponentStatus.OK),
    )
    reporter = RuntimeComponentHealthReporter(
        sealed_registry(timeout, failed, invalid, mismatched),
        timeout_seconds=0.001,
    )

    report = asyncio.run(reporter.report())

    assert report.status is RuntimeComponentStatus.UNAVAILABLE
    assert [(component.name, component.reason) for component in report.components] == [
        ("timeout", COMPONENT_HEALTH_TIMEOUT),
        ("failed", COMPONENT_HEALTH_CHECK_FAILED),
        ("invalid", COMPONENT_HEALTH_CHECK_FAILED),
        ("expected", COMPONENT_HEALTH_CHECK_FAILED),
    ]


def test_native_cancellation_is_preserved() -> None:
    """A component cancellation must not become an unavailable health value."""
    service = HealthRuntimeService("cancelled", asyncio.CancelledError())
    reporter = RuntimeComponentHealthReporter(sealed_registry(service))

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(reporter.report())


def test_concurrent_reporters_serialize_but_later_reports_are_fresh() -> None:
    """Concurrent callers should share exclusion without caching later results."""
    entered = asyncio.Event()
    release = asyncio.Event()
    active = 0
    maximum_active = 0

    class SerialHealthService(StubRuntimeService):
        def __init__(self) -> None:
            super().__init__("serial")
            self.calls = 0

        async def check_health(self) -> RuntimeComponentHealth:
            nonlocal active, maximum_active
            self.calls += 1
            active += 1
            maximum_active = max(maximum_active, active)
            entered.set()
            await release.wait()
            active -= 1
            return RuntimeComponentHealth(name=self.name, status=RuntimeComponentStatus.OK)

    service = SerialHealthService()
    reporter = RuntimeComponentHealthReporter(sealed_registry(service))

    async def exercise() -> None:
        first = asyncio.create_task(reporter.report())
        await entered.wait()
        second = asyncio.create_task(reporter.report())
        await asyncio.sleep(0)
        assert service.calls == 1
        release.set()
        await asyncio.gather(first, second)
        await reporter.report()

    asyncio.run(exercise())

    assert service.calls == 3
    assert maximum_active == 1


def test_transition_logs_are_bounded_and_not_repeated() -> None:
    """Repeated states should log once without raw failure information."""
    output = io.StringIO()
    configure_logging(stream=output)
    service = HealthRuntimeService(
        "database",
        RuntimeError("credential at https://private.example"),
    )
    reporter = RuntimeComponentHealthReporter(sealed_registry(service))

    async def exercise() -> None:
        await reporter.report()
        await reporter.report()
        service.result = RuntimeComponentHealth(
            name="database",
            status=RuntimeComponentStatus.OK,
        )
        await reporter.report()

    asyncio.run(exercise())
    payloads = [json.loads(line) for line in output.getvalue().splitlines()]

    assert len(payloads) == 2
    assert payloads[0]["event"] == "runtime.component.health.unavailable"
    assert payloads[0]["runtime_service"] == "database"
    assert payloads[0]["outcome"] == "unavailable"
    assert payloads[0]["error_code"] == COMPONENT_HEALTH_CHECK_FAILED
    assert payloads[0]["error_type"] == "RuntimeError"
    assert payloads[1]["event"] == "runtime.component.health.ok"
    assert payloads[1]["outcome"] == "ok"
    assert "error_code" not in payloads[1]
    assert "credential" not in output.getvalue()
    assert "private.example" not in output.getvalue()
