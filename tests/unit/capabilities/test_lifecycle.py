"""Tests for deterministic registered capability lifecycle management."""

import asyncio
import io
import json
from math import inf, nan
from typing import cast

import pytest

from trussium.capabilities import (
    CapabilityLifecycle,
    CapabilityLifecycleError,
    CapabilityLifecyclePhase,
    CapabilityLifecycleRegistration,
    CapabilityLifecycleState,
    CapabilityLifecycleStateError,
    CapabilityRegistry,
    LifecycleCapability,
)
from trussium.errors import LifecycleError, TrussiumError
from trussium.observability import configure_logging


class StubLifecycleCapability:
    """Controllable lifecycle-aware capability used by coordinator tests."""

    def __init__(
        self,
        name: str,
        events: list[str],
        *,
        startup_error: BaseException | None = None,
        shutdown_error: BaseException | None = None,
        shutdown_delay: float = 0.0,
    ) -> None:
        """Initialize hook behavior and event recording."""
        self.name = name
        self.events = events
        self.startup_error = startup_error
        self.shutdown_error = shutdown_error
        self.shutdown_delay = shutdown_delay
        self.startup_calls = 0
        self.shutdown_calls = 0

    async def startup(self) -> None:
        """Record startup and raise the configured failure."""
        self.startup_calls += 1
        self.events.append(f"start:{self.name}")
        if self.startup_error is not None:
            raise self.startup_error

    async def shutdown(self) -> None:
        """Record shutdown and raise the configured failure."""
        self.shutdown_calls += 1
        self.events.append(f"stop:{self.name}")
        if self.shutdown_delay:
            await asyncio.sleep(self.shutdown_delay)
        if self.shutdown_error is not None:
            raise self.shutdown_error


def lifecycle_for(
    *capabilities: tuple[str, object],
    cleanup_timeout_seconds: float = 10.0,
) -> CapabilityLifecycle:
    """Build a sealed registry-backed lifecycle for tests."""
    registry = CapabilityRegistry()
    for name, capability in capabilities:
        registry.register(name, capability)
    registry.seal()
    return CapabilityLifecycle(
        registry,
        cleanup_timeout_seconds=cleanup_timeout_seconds,
    )


def assert_lifecycle_state(
    lifecycle: CapabilityLifecycle,
    expected: CapabilityLifecycleState,
) -> None:
    """Assert state without narrowing later asynchronous transitions."""
    assert lifecycle.state is expected


def test_lifecycle_filters_optional_hooks_and_preserves_registry_order() -> None:
    """Only structural hook implementations belong to the immutable plan."""
    events: list[str] = []
    first = StubLifecycleCapability("first", events)
    second = StubLifecycleCapability("second", events)
    lifecycle = lifecycle_for(
        ("first", first),
        ("ordinary", object()),
        ("second", second),
        cleanup_timeout_seconds=0.5,
    )

    assert isinstance(first, LifecycleCapability)
    assert not isinstance(object(), LifecycleCapability)
    assert lifecycle.names == ("first", "second")
    assert tuple(item.capability for item in lifecycle.registrations) == (first, second)
    assert lifecycle.cleanup_timeout_seconds == 0.5

    async def exercise() -> None:
        assert_lifecycle_state(lifecycle, CapabilityLifecycleState.INITIALIZED)
        await lifecycle.startup()
        assert_lifecycle_state(lifecycle, CapabilityLifecycleState.STARTED)
        await lifecycle.shutdown()

    asyncio.run(exercise())

    assert_lifecycle_state(lifecycle, CapabilityLifecycleState.STOPPED)
    assert events == ["start:first", "start:second", "stop:second", "stop:first"]
    assert first.startup_calls == first.shutdown_calls == 1
    assert second.startup_calls == second.shutdown_calls == 1


def test_empty_plan_starts_and_stops_without_hooks() -> None:
    """Registries without lifecycle-aware capabilities remain compatible."""
    lifecycle = lifecycle_for(("ordinary", object()))

    async def exercise() -> None:
        await lifecycle.startup()
        await lifecycle.shutdown()

    asyncio.run(exercise())

    assert lifecycle.names == ()
    assert lifecycle.state is CapabilityLifecycleState.STOPPED


@pytest.mark.parametrize("timeout", [0.0, -1.0, inf, -inf, nan])
def test_cleanup_timeout_must_be_positive_and_finite(timeout: float) -> None:
    """Cleanup cannot be unbounded, non-positive, or non-finite."""
    with pytest.raises(ValueError, match="finite and positive"):
        lifecycle_for(cleanup_timeout_seconds=timeout)


def test_lifecycle_requires_a_sealed_registry() -> None:
    """An open registry cannot define immutable application ownership."""
    with pytest.raises(ValueError, match="sealed registry"):
        CapabilityLifecycle(CapabilityRegistry())


def test_registration_validates_identity_and_contract() -> None:
    """Direct immutable plan values retain bounded public validation."""
    events: list[str] = []
    capability = StubLifecycleCapability("valid", events)
    registration = CapabilityLifecycleRegistration("valid", capability)
    assert registration.name == "valid"
    assert registration.capability is capability

    with pytest.raises(ValueError, match="Capability name"):
        CapabilityLifecycleRegistration("Invalid Name", capability)
    with pytest.raises(TypeError, match=r"startup.*shutdown"):
        CapabilityLifecycleRegistration(
            "valid",
            cast(LifecycleCapability, object()),
        )


def test_partial_startup_failure_rolls_back_only_started_capabilities() -> None:
    """Startup stops at failure and aggregates bounded rollback failures."""
    events: list[str] = []
    first = StubLifecycleCapability(
        "first",
        events,
        shutdown_error=RuntimeError("private rollback detail"),
    )
    second = StubLifecycleCapability(
        "second",
        events,
        startup_error=ValueError("private startup detail"),
    )
    third = StubLifecycleCapability("third", events)
    lifecycle = lifecycle_for(("first", first), ("second", second), ("third", third))

    with pytest.raises(CapabilityLifecycleError) as captured:
        asyncio.run(lifecycle.startup())

    error = captured.value
    assert isinstance(error, LifecycleError)
    assert isinstance(error, TrussiumError)
    assert error.phase is CapabilityLifecyclePhase.STARTUP
    assert error.code == "capability_startup_failed"
    assert error.message == "Capability startup failed for 2 capability(s)."
    assert [
        (failure.capability_name, failure.phase, failure.code, failure.error_type)
        for failure in error.failures
    ] == [
        (
            "second",
            CapabilityLifecyclePhase.STARTUP,
            "capability_startup_failed",
            "ValueError",
        ),
        (
            "first",
            CapabilityLifecyclePhase.ROLLBACK,
            "capability_rollback_failed",
            "RuntimeError",
        ),
    ]
    assert lifecycle.state is CapabilityLifecycleState.FAILED
    assert events == ["start:first", "start:second", "stop:first"]
    assert second.shutdown_calls == 0
    assert third.startup_calls == third.shutdown_calls == 0


def test_shutdown_continues_and_aggregates_multiple_failures() -> None:
    """Independent cleanup failures must not skip remaining hooks."""
    events: list[str] = []
    first = StubLifecycleCapability(
        "first", events, shutdown_error=ValueError("private first detail")
    )
    second = StubLifecycleCapability(
        "second", events, shutdown_error=RuntimeError("private second detail")
    )
    lifecycle = lifecycle_for(("first", first), ("second", second))

    async def exercise() -> CapabilityLifecycleError:
        await lifecycle.startup()
        with pytest.raises(CapabilityLifecycleError) as captured:
            await lifecycle.shutdown()
        return captured.value

    error = asyncio.run(exercise())

    assert error.phase is CapabilityLifecyclePhase.SHUTDOWN
    assert [failure.capability_name for failure in error.failures] == ["second", "first"]
    assert [failure.error_type for failure in error.failures] == [
        "RuntimeError",
        "ValueError",
    ]
    assert events == ["start:first", "start:second", "stop:second", "stop:first"]
    assert lifecycle.state is CapabilityLifecycleState.FAILED


def test_cleanup_timeout_is_bounded_and_remaining_hooks_run() -> None:
    """An unresponsive hook is cancelled without blocking later cleanup."""
    events: list[str] = []
    healthy = StubLifecycleCapability("healthy", events)
    slow = StubLifecycleCapability("slow", events, shutdown_delay=1.0)
    lifecycle = lifecycle_for(
        ("healthy", healthy),
        ("slow", slow),
        cleanup_timeout_seconds=0.001,
    )

    async def exercise() -> CapabilityLifecycleError:
        await lifecycle.startup()
        with pytest.raises(CapabilityLifecycleError) as captured:
            await lifecycle.shutdown()
        await asyncio.sleep(0)
        return captured.value

    error = asyncio.run(exercise())

    assert [
        (failure.capability_name, failure.code, failure.error_type) for failure in error.failures
    ] == [("slow", "capability_shutdown_timeout", "TimeoutError")]
    assert events == ["start:healthy", "start:slow", "stop:slow", "stop:healthy"]


def test_startup_cancellation_rolls_back_and_remains_cancellation() -> None:
    """Native cancellation retains its identity after bounded rollback."""
    events: list[str] = []
    first = StubLifecycleCapability("first", events)
    cancelled = StubLifecycleCapability("cancelled", events, startup_error=asyncio.CancelledError())
    lifecycle = lifecycle_for(("first", first), ("cancelled", cancelled))

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(lifecycle.startup())

    assert events == ["start:first", "start:cancelled", "stop:first"]
    assert lifecycle.state is CapabilityLifecycleState.FAILED


def test_shutdown_cancellation_does_not_skip_remaining_capabilities() -> None:
    """Cleanup continues before propagating a hook cancellation."""
    events: list[str] = []
    remaining = StubLifecycleCapability("remaining", events)
    cancelled = StubLifecycleCapability(
        "cancelled", events, shutdown_error=asyncio.CancelledError()
    )
    lifecycle = lifecycle_for(("remaining", remaining), ("cancelled", cancelled))

    async def exercise() -> None:
        await lifecycle.startup()
        await lifecycle.shutdown()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(exercise())

    assert events == [
        "start:remaining",
        "start:cancelled",
        "stop:cancelled",
        "stop:remaining",
    ]
    assert lifecycle.state is CapabilityLifecycleState.FAILED


def test_invalid_transitions_never_rerun_hooks() -> None:
    """Repeated and out-of-order operations fail deterministically."""
    events: list[str] = []
    capability = StubLifecycleCapability("capability", events)
    lifecycle = lifecycle_for(("capability", capability))

    with pytest.raises(CapabilityLifecycleStateError) as before_startup:
        asyncio.run(lifecycle.shutdown())
    assert before_startup.value.state is CapabilityLifecycleState.INITIALIZED
    assert before_startup.value.code == "capability_lifecycle_state_invalid"

    async def exercise() -> None:
        await lifecycle.startup()
        with pytest.raises(CapabilityLifecycleStateError):
            await lifecycle.startup()
        await lifecycle.shutdown()
        with pytest.raises(CapabilityLifecycleStateError):
            await lifecycle.shutdown()

    asyncio.run(exercise())
    assert events == ["start:capability", "stop:capability"]


def test_operational_events_are_ordered_bounded_and_private() -> None:
    """Lifecycle logs expose stable fields without raw hook exception text."""
    output = io.StringIO()
    configure_logging(stream=output)
    events: list[str] = []
    first = StubLifecycleCapability("first", events)
    second = StubLifecycleCapability(
        "second", events, startup_error=RuntimeError("secret lifecycle detail")
    )
    lifecycle = lifecycle_for(("first", first), ("second", second))

    with pytest.raises(CapabilityLifecycleError):
        asyncio.run(lifecycle.startup())

    payloads = [json.loads(line) for line in output.getvalue().splitlines()]
    assert [payload["event"] for payload in payloads] == [
        "capability.startup.started",
        "capability.startup.completed",
        "capability.startup.started",
        "capability.startup.failed",
        "capability.rollback.started",
        "capability.rollback.completed",
    ]
    assert [payload["capability"] for payload in payloads] == [
        "first",
        "first",
        "second",
        "second",
        "first",
        "first",
    ]
    failed = payloads[3]
    assert failed["lifecycle_phase"] == "startup"
    assert failed["error_code"] == "capability_startup_failed"
    assert failed["error_type"] == "RuntimeError"
    assert failed["outcome"] == "failed"
    assert isinstance(failed["duration_ms"], float)
    assert "secret lifecycle detail" not in output.getvalue()
