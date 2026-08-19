"""Tests for deterministic capability availability reporting."""

import asyncio
import io
import json
from math import inf, nan
from typing import cast

import pytest

from trussium.capabilities import (
    CAPABILITY_AVAILABILITY_CHECK_FAILED,
    CAPABILITY_AVAILABILITY_TIMEOUT,
    CapabilityAvailability,
    CapabilityAvailabilityReporter,
    CapabilityAvailabilityStatus,
    CapabilityRegistry,
)
from trussium.observability import configure_logging


class AvailabilityCapability:
    """Capability returning a configured availability result or failure."""

    def __init__(
        self,
        result: CapabilityAvailability | BaseException | object,
        *,
        delay: float = 0.0,
    ) -> None:
        self.result = result
        self.delay = delay
        self.calls = 0

    async def check_availability(self) -> CapabilityAvailability:
        """Return or raise the configured result."""
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if isinstance(self.result, BaseException):
            raise self.result
        return cast(CapabilityAvailability, self.result)


def sealed_registry(*registrations: tuple[str, object]) -> CapabilityRegistry:
    """Return a capability registry sealed in the supplied order."""
    registry = CapabilityRegistry()
    for name, capability in registrations:
        registry.register(name, capability)
    registry.seal()
    return registry


def test_availability_values_enforce_bounded_semantics() -> None:
    """Availability values should reject unsafe identities and reason states."""
    assert CapabilityAvailability(
        name="chat.completions",
        status=CapabilityAvailabilityStatus.AVAILABLE,
    ) == CapabilityAvailability(
        name="chat.completions",
        status=CapabilityAvailabilityStatus.AVAILABLE,
    )

    with pytest.raises(ValueError, match="must match"):
        CapabilityAvailability(name="UPPER", status=CapabilityAvailabilityStatus.AVAILABLE)
    with pytest.raises(ValueError, match="must not include"):
        CapabilityAvailability(
            name="chat",
            status=CapabilityAvailabilityStatus.AVAILABLE,
            reason="unexpected_reason",
        )
    with pytest.raises(ValueError, match="reasons must match"):
        CapabilityAvailability(name="chat", status=CapabilityAvailabilityStatus.UNAVAILABLE)
    with pytest.raises(ValueError, match="reasons must match"):
        CapabilityAvailability(
            name="chat",
            status=CapabilityAvailabilityStatus.UNAVAILABLE,
            reason="private detail",
        )
    with pytest.raises(ValueError, match="CapabilityAvailabilityStatus"):
        CapabilityAvailability(
            name="chat",
            status=cast(CapabilityAvailabilityStatus, "available"),
        )


@pytest.mark.parametrize("timeout", [0.0, -1.0, inf, nan])
def test_reporter_requires_sealed_registry_and_positive_deadline(timeout: float) -> None:
    """Reporting ownership and deadlines should fail before evaluation."""
    with pytest.raises(ValueError, match="sealed registry"):
        CapabilityAvailabilityReporter(CapabilityRegistry())

    with pytest.raises(ValueError, match="finite and positive"):
        CapabilityAvailabilityReporter(sealed_registry(), timeout_seconds=timeout)


def test_empty_registry_and_ordinary_capabilities_default_available() -> None:
    """Registration alone should be sufficient for informational availability."""
    empty_registry = sealed_registry()
    empty_reporter = CapabilityAvailabilityReporter(empty_registry, timeout_seconds=0.5)

    empty_report = asyncio.run(empty_reporter.report())
    ordinary_report = asyncio.run(
        CapabilityAvailabilityReporter(sealed_registry(("future.images", object()))).report()
    )

    assert empty_reporter.registry is empty_registry
    assert empty_reporter.timeout_seconds == 0.5
    assert empty_report.status is CapabilityAvailabilityStatus.AVAILABLE
    assert empty_report.capabilities == ()
    assert ordinary_report == type(ordinary_report)(
        status=CapabilityAvailabilityStatus.AVAILABLE,
        capabilities=(
            CapabilityAvailability(
                name="future.images",
                status=CapabilityAvailabilityStatus.AVAILABLE,
            ),
        ),
    )


def test_order_and_aggregate_are_deterministic_with_concurrent_checks() -> None:
    """Completion timing must not alter output order or aggregate status."""
    both_started = asyncio.Event()
    started = 0

    class ConcurrentCapability:
        def __init__(self, name: str, status: CapabilityAvailabilityStatus) -> None:
            self.name = name
            self.status = status

        async def check_availability(self) -> CapabilityAvailability:
            nonlocal started
            started += 1
            if started == 2:
                both_started.set()
            await both_started.wait()
            return CapabilityAvailability(
                name=self.name,
                status=self.status,
                reason=(
                    "provider_offline"
                    if self.status is not CapabilityAvailabilityStatus.AVAILABLE
                    else None
                ),
            )

    reporter = CapabilityAvailabilityReporter(
        sealed_registry(
            ("first", ConcurrentCapability("first", CapabilityAvailabilityStatus.AVAILABLE)),
            ("second", ConcurrentCapability("second", CapabilityAvailabilityStatus.UNAVAILABLE)),
        ),
        timeout_seconds=1.0,
    )

    report = asyncio.run(reporter.report())

    assert report.status is CapabilityAvailabilityStatus.UNAVAILABLE
    assert [capability.name for capability in report.capabilities] == ["first", "second"]


def test_timeout_exception_invalid_and_mismatched_results_are_normalized() -> None:
    """Owned failure boundaries should return stable safe availability states."""
    reporter = CapabilityAvailabilityReporter(
        sealed_registry(
            (
                "timeout",
                AvailabilityCapability(
                    CapabilityAvailability(
                        name="timeout",
                        status=CapabilityAvailabilityStatus.AVAILABLE,
                    ),
                    delay=1.0,
                ),
            ),
            ("failed", AvailabilityCapability(RuntimeError("private credential"))),
            ("invalid", AvailabilityCapability(object())),
            (
                "expected",
                AvailabilityCapability(
                    CapabilityAvailability(
                        name="other",
                        status=CapabilityAvailabilityStatus.AVAILABLE,
                    )
                ),
            ),
        ),
        timeout_seconds=0.001,
    )

    report = asyncio.run(reporter.report())

    assert report.status is CapabilityAvailabilityStatus.UNAVAILABLE
    assert [(item.name, item.reason) for item in report.capabilities] == [
        ("timeout", CAPABILITY_AVAILABILITY_TIMEOUT),
        ("failed", CAPABILITY_AVAILABILITY_CHECK_FAILED),
        ("invalid", CAPABILITY_AVAILABILITY_CHECK_FAILED),
        ("expected", CAPABILITY_AVAILABILITY_CHECK_FAILED),
    ]


def test_native_cancellation_is_preserved() -> None:
    """Cancellation must not become an unavailable availability value."""
    reporter = CapabilityAvailabilityReporter(
        sealed_registry(("cancelled", AvailabilityCapability(asyncio.CancelledError())))
    )

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(reporter.report())


def test_concurrent_reports_serialize_and_each_report_is_fresh() -> None:
    """Concurrent callers should not overlap checks or receive cached results."""
    entered = asyncio.Event()
    release = asyncio.Event()
    active = 0
    maximum_active = 0

    class SerialCapability:
        def __init__(self) -> None:
            self.calls = 0

        async def check_availability(self) -> CapabilityAvailability:
            nonlocal active, maximum_active
            self.calls += 1
            active += 1
            maximum_active = max(maximum_active, active)
            entered.set()
            await release.wait()
            active -= 1
            return CapabilityAvailability(
                name="serial",
                status=CapabilityAvailabilityStatus.AVAILABLE,
            )

    capability = SerialCapability()
    reporter = CapabilityAvailabilityReporter(sealed_registry(("serial", capability)))

    async def exercise() -> None:
        first = asyncio.create_task(reporter.report())
        await entered.wait()
        second = asyncio.create_task(reporter.report())
        await asyncio.sleep(0)
        assert capability.calls == 1
        release.set()
        await asyncio.gather(first, second)
        await reporter.report()

    asyncio.run(exercise())

    assert capability.calls == 3
    assert maximum_active == 1


def test_transition_logs_are_bounded_and_not_repeated() -> None:
    """Repeated states should log once without raw failure information."""
    output = io.StringIO()
    configure_logging(stream=output)
    capability = AvailabilityCapability(RuntimeError("secret at https://private.example"))
    reporter = CapabilityAvailabilityReporter(sealed_registry(("chat", capability)))

    async def exercise() -> None:
        await reporter.report()
        await reporter.report()
        capability.result = CapabilityAvailability(
            name="chat",
            status=CapabilityAvailabilityStatus.AVAILABLE,
        )
        await reporter.report()

    asyncio.run(exercise())
    payloads = [json.loads(line) for line in output.getvalue().splitlines()]

    assert len(payloads) == 2
    assert payloads[0]["event"] == "capability.availability.unavailable"
    assert payloads[0]["capability"] == "chat"
    assert payloads[0]["outcome"] == "unavailable"
    assert payloads[0]["error_code"] == CAPABILITY_AVAILABILITY_CHECK_FAILED
    assert payloads[0]["error_type"] == "RuntimeError"
    assert payloads[1]["event"] == "capability.availability.available"
    assert payloads[1]["outcome"] == "available"
    assert "error_code" not in payloads[1]
    assert "secret" not in output.getvalue()
    assert "private.example" not in output.getvalue()
