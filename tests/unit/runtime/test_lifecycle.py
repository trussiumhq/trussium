"""Tests for deterministic runtime-service lifecycle hooks."""

import asyncio
import io
import json
from math import inf, nan

import pytest

from trussium.errors import LifecycleError, TrussiumError
from trussium.observability import configure_logging
from trussium.runtime import (
    RuntimeServiceLifecycle,
    RuntimeServiceLifecycleError,
    RuntimeServiceLifecyclePhase,
    RuntimeServiceLifecycleState,
    RuntimeServiceStateError,
)


class StubRuntimeService:
    """Controllable runtime service used by lifecycle tests."""

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


def assert_lifecycle_state(
    lifecycle: RuntimeServiceLifecycle,
    expected: RuntimeServiceLifecycleState,
) -> None:
    """Assert state without narrowing later asynchronous transitions."""
    assert lifecycle.state is expected


def test_services_start_in_order_and_stop_once_in_reverse_order() -> None:
    """The immutable lifecycle plan should run deterministic hook ordering."""
    events: list[str] = []
    first = StubRuntimeService("first", events)
    second = StubRuntimeService("second", events)
    configured_services = [first, second]
    lifecycle = RuntimeServiceLifecycle(
        configured_services,
        cleanup_timeout_seconds=0.5,
    )
    configured_services.clear()

    async def exercise() -> None:
        assert_lifecycle_state(lifecycle, RuntimeServiceLifecycleState.INITIALIZED)
        await lifecycle.startup()
        assert_lifecycle_state(lifecycle, RuntimeServiceLifecycleState.STARTED)
        await lifecycle.shutdown()

    asyncio.run(exercise())

    assert lifecycle.services == (first, second)
    assert lifecycle.cleanup_timeout_seconds == 0.5
    assert_lifecycle_state(lifecycle, RuntimeServiceLifecycleState.STOPPED)
    assert events == ["start:first", "start:second", "stop:second", "stop:first"]
    assert first.startup_calls == first.shutdown_calls == 1
    assert second.startup_calls == second.shutdown_calls == 1


def test_partial_startup_failure_rolls_back_only_started_services() -> None:
    """Startup should stop at the failure and roll back prior services only."""
    events: list[str] = []
    first = StubRuntimeService(
        "first",
        events,
        shutdown_error=RuntimeError("private rollback detail"),
    )
    second = StubRuntimeService(
        "second",
        events,
        startup_error=ValueError("private startup detail"),
    )
    third = StubRuntimeService("third", events)
    lifecycle = RuntimeServiceLifecycle((first, second, third))

    with pytest.raises(RuntimeServiceLifecycleError) as captured:
        asyncio.run(lifecycle.startup())

    error = captured.value
    assert isinstance(error, LifecycleError)
    assert isinstance(error, TrussiumError)
    assert error.phase is RuntimeServiceLifecyclePhase.STARTUP
    assert error.code == "runtime_service_startup_failed"
    assert error.message == "Runtime service startup failed for 2 service(s)."
    assert [
        (failure.service_name, failure.phase, failure.code, failure.error_type)
        for failure in error.failures
    ] == [
        (
            "second",
            RuntimeServiceLifecyclePhase.STARTUP,
            "runtime_service_startup_failed",
            "ValueError",
        ),
        (
            "first",
            RuntimeServiceLifecyclePhase.ROLLBACK,
            "runtime_service_rollback_failed",
            "RuntimeError",
        ),
    ]
    assert lifecycle.state is RuntimeServiceLifecycleState.FAILED
    assert events == ["start:first", "start:second", "stop:first"]
    assert second.shutdown_calls == 0
    assert third.startup_calls == third.shutdown_calls == 0


def test_shutdown_continues_after_multiple_failures() -> None:
    """Independent cleanup failures must not prevent remaining hooks."""
    events: list[str] = []
    first = StubRuntimeService(
        "first",
        events,
        shutdown_error=ValueError("private first detail"),
    )
    second = StubRuntimeService(
        "second",
        events,
        shutdown_error=RuntimeError("private second detail"),
    )
    lifecycle = RuntimeServiceLifecycle((first, second))

    async def exercise() -> RuntimeServiceLifecycleError:
        await lifecycle.startup()
        with pytest.raises(RuntimeServiceLifecycleError) as captured:
            await lifecycle.shutdown()
        return captured.value

    error = asyncio.run(exercise())

    assert error.phase is RuntimeServiceLifecyclePhase.SHUTDOWN
    assert [failure.service_name for failure in error.failures] == ["second", "first"]
    assert [failure.error_type for failure in error.failures] == [
        "RuntimeError",
        "ValueError",
    ]
    assert events == ["start:first", "start:second", "stop:second", "stop:first"]
    assert lifecycle.state is RuntimeServiceLifecycleState.FAILED


def test_cleanup_timeout_is_bounded_and_remaining_hooks_run() -> None:
    """An unresponsive hook should be cancelled without blocking later cleanup."""
    events: list[str] = []
    healthy = StubRuntimeService("healthy", events)
    slow = StubRuntimeService("slow", events, shutdown_delay=1.0)
    lifecycle = RuntimeServiceLifecycle(
        (healthy, slow),
        cleanup_timeout_seconds=0.001,
    )

    async def exercise() -> RuntimeServiceLifecycleError:
        await lifecycle.startup()
        with pytest.raises(RuntimeServiceLifecycleError) as captured:
            await lifecycle.shutdown()
        await asyncio.sleep(0)
        return captured.value

    error = asyncio.run(exercise())

    assert [
        (failure.service_name, failure.code, failure.error_type) for failure in error.failures
    ] == [("slow", "runtime_service_shutdown_timeout", "TimeoutError")]
    assert events == ["start:healthy", "start:slow", "stop:slow", "stop:healthy"]
    assert healthy.shutdown_calls == slow.shutdown_calls == 1


def test_startup_cancellation_rolls_back_and_remains_cancellation() -> None:
    """Native cancellation should retain its identity after bounded rollback."""
    events: list[str] = []
    first = StubRuntimeService("first", events)
    cancelled = StubRuntimeService(
        "cancelled",
        events,
        startup_error=asyncio.CancelledError(),
    )
    lifecycle = RuntimeServiceLifecycle((first, cancelled))

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(lifecycle.startup())

    assert events == ["start:first", "start:cancelled", "stop:first"]
    assert lifecycle.state is RuntimeServiceLifecycleState.FAILED


def test_shutdown_cancellation_does_not_skip_remaining_services() -> None:
    """Cleanup should continue before propagating a hook cancellation."""
    events: list[str] = []
    remaining = StubRuntimeService("remaining", events)
    cancelled = StubRuntimeService(
        "cancelled",
        events,
        shutdown_error=asyncio.CancelledError(),
    )
    lifecycle = RuntimeServiceLifecycle((remaining, cancelled))

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
    assert lifecycle.state is RuntimeServiceLifecycleState.FAILED


def test_invalid_transitions_do_not_rerun_hooks() -> None:
    """Repeated and out-of-order operations should fail deterministically."""
    events: list[str] = []
    service = StubRuntimeService("service", events)
    lifecycle = RuntimeServiceLifecycle((service,))

    with pytest.raises(RuntimeServiceStateError) as before_startup:
        asyncio.run(lifecycle.shutdown())
    assert before_startup.value.state is RuntimeServiceLifecycleState.INITIALIZED
    assert before_startup.value.code == "runtime_service_state_invalid"

    async def exercise() -> None:
        await lifecycle.startup()
        with pytest.raises(RuntimeServiceStateError):
            await lifecycle.startup()
        await lifecycle.shutdown()
        with pytest.raises(RuntimeServiceStateError):
            await lifecycle.shutdown()

    asyncio.run(exercise())

    assert events == ["start:service", "stop:service"]


@pytest.mark.parametrize("timeout", [0.0, -1.0, inf, nan])
def test_invalid_cleanup_deadlines_are_rejected(timeout: float) -> None:
    """Direct coordinator use should reject non-positive or unbounded deadlines."""
    with pytest.raises(ValueError, match="finite and positive"):
        RuntimeServiceLifecycle(cleanup_timeout_seconds=timeout)


@pytest.mark.parametrize("name", ["", "UPPER", "has space", "a" * 65])
def test_unsafe_service_names_are_rejected(name: str) -> None:
    """Operational service names must be stable and safe to serialize."""
    with pytest.raises(ValueError, match="must match"):
        RuntimeServiceLifecycle((StubRuntimeService(name, []),))


def test_duplicate_service_names_are_rejected() -> None:
    """Ambiguous service identities should fail before startup."""
    with pytest.raises(ValueError, match="must be unique"):
        RuntimeServiceLifecycle(
            (
                StubRuntimeService("duplicate", []),
                StubRuntimeService("duplicate", []),
            )
        )


def test_operational_events_are_ordered_and_exclude_raw_failures() -> None:
    """Lifecycle logs should expose bounded metadata without exception text."""
    output = io.StringIO()
    configure_logging(stream=output)
    events: list[str] = []
    service = StubRuntimeService(
        "cache",
        events,
        shutdown_error=RuntimeError("credential at private endpoint"),
    )
    lifecycle = RuntimeServiceLifecycle((service,))

    async def exercise() -> None:
        await lifecycle.startup()
        with pytest.raises(RuntimeServiceLifecycleError):
            await lifecycle.shutdown()

    asyncio.run(exercise())
    payloads = [json.loads(line) for line in output.getvalue().splitlines()]

    assert [payload["event"] for payload in payloads] == [
        "runtime.service.startup.started",
        "runtime.service.startup.completed",
        "runtime.service.shutdown.started",
        "runtime.service.shutdown.failed",
    ]
    assert payloads[-1]["runtime_service"] == "cache"
    assert payloads[-1]["lifecycle_phase"] == "shutdown"
    assert payloads[-1]["error_code"] == "runtime_service_shutdown_failed"
    assert payloads[-1]["error_type"] == "RuntimeError"
    assert payloads[-1]["outcome"] == "failed"
    assert "credential" not in output.getvalue()
    assert "private endpoint" not in output.getvalue()
