"""Deterministic lifecycle management for registered capabilities."""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from time import perf_counter
from typing import Protocol, runtime_checkable

from trussium.capabilities.registry import CapabilityRegistry, validate_capability_name
from trussium.errors import LifecycleError
from trussium.observability.logging import get_logger
from trussium.observability.operations import (
    CAPABILITY_ROLLBACK_CANCELLED,
    CAPABILITY_ROLLBACK_COMPLETED,
    CAPABILITY_ROLLBACK_FAILED,
    CAPABILITY_ROLLBACK_STARTED,
    CAPABILITY_ROLLBACK_TIMEOUT,
    CAPABILITY_SHUTDOWN_CANCELLED,
    CAPABILITY_SHUTDOWN_COMPLETED,
    CAPABILITY_SHUTDOWN_FAILED,
    CAPABILITY_SHUTDOWN_STARTED,
    CAPABILITY_SHUTDOWN_TIMEOUT,
    CAPABILITY_STARTUP_CANCELLED,
    CAPABILITY_STARTUP_COMPLETED,
    CAPABILITY_STARTUP_FAILED,
    CAPABILITY_STARTUP_STARTED,
)


@runtime_checkable
class LifecycleCapability(Protocol):
    """Optional asynchronous resource hooks for a registered capability."""

    async def startup(self) -> None:
        """Initialize application-scoped capability resources."""
        ...

    async def shutdown(self) -> None:
        """Release application-scoped capability resources."""
        ...


class CapabilityLifecycleState(StrEnum):
    """Deterministic states for the capability lifecycle coordinator."""

    INITIALIZED = "initialized"
    STARTING = "starting"
    STARTED = "started"
    ROLLING_BACK = "rolling_back"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class CapabilityLifecyclePhase(StrEnum):
    """Lifecycle phases exposed by failures and operational events."""

    STARTUP = "startup"
    ROLLBACK = "rollback"
    SHUTDOWN = "shutdown"


@dataclass(frozen=True, slots=True)
class CapabilityLifecycleRegistration:
    """Immutable canonical identity and lifecycle-hook association."""

    name: str
    capability: LifecycleCapability

    def __post_init__(self) -> None:
        """Validate the canonical registry identity and hook contract."""
        validate_capability_name(self.name)
        if not isinstance(self.capability, LifecycleCapability):
            raise TypeError("Lifecycle capability must implement startup() and shutdown()")


@dataclass(frozen=True, slots=True)
class CapabilityLifecycleFailure:
    """Bounded description of one failed capability lifecycle hook."""

    capability_name: str
    phase: CapabilityLifecyclePhase
    code: str
    error_type: str


class CapabilityLifecycleError(LifecycleError):
    """Aggregate failure raised after all eligible lifecycle hooks run."""

    def __init__(
        self,
        phase: CapabilityLifecyclePhase,
        failures: Sequence[CapabilityLifecycleFailure],
    ) -> None:
        """Initialize a bounded lifecycle failure without raw exception text."""
        resolved_failures = tuple(failures)
        if not resolved_failures:
            raise ValueError("Lifecycle failures must not be empty")

        super().__init__(
            f"Capability {phase.value} failed for {len(resolved_failures)} capability(s).",
            code=f"capability_{phase.value}_failed",
        )
        self.phase = phase
        self.failures = resolved_failures


class CapabilityLifecycleStateError(LifecycleError):
    """Invalid coordinator transition that never re-runs lifecycle hooks."""

    default_code = "capability_lifecycle_state_invalid"

    def __init__(
        self,
        *,
        operation: CapabilityLifecyclePhase,
        state: CapabilityLifecycleState,
    ) -> None:
        """Initialize an invalid transition error with bounded state metadata."""
        super().__init__(f"Capability {operation.value} is invalid from state {state.value}.")
        self.operation = operation
        self.state = state


class CapabilityLifecycle:
    """Run optional registered capability hooks with bounded cleanup."""

    def __init__(
        self,
        registry: CapabilityRegistry,
        *,
        cleanup_timeout_seconds: float = 10.0,
    ) -> None:
        """Derive an immutable lifecycle plan from a sealed registry snapshot."""
        if not registry.sealed:
            raise ValueError("Capability lifecycle requires a sealed registry")
        if not isfinite(cleanup_timeout_seconds) or cleanup_timeout_seconds <= 0:
            raise ValueError("Cleanup timeout must be finite and positive")

        self._registrations = tuple(
            CapabilityLifecycleRegistration(registration.name, registration.capability)
            for registration in registry.registrations
            if isinstance(registration.capability, LifecycleCapability)
        )
        self._cleanup_timeout_seconds = cleanup_timeout_seconds
        self._state = CapabilityLifecycleState.INITIALIZED
        self._started: list[CapabilityLifecycleRegistration] = []
        self._logger = get_logger("capability.lifecycle")

    @property
    def registrations(self) -> tuple[CapabilityLifecycleRegistration, ...]:
        """Return the immutable ordered lifecycle plan."""
        return self._registrations

    @property
    def names(self) -> tuple[str, ...]:
        """Return immutable canonical identities in lifecycle order."""
        return tuple(registration.name for registration in self._registrations)

    @property
    def cleanup_timeout_seconds(self) -> float:
        """Return the per-capability cleanup deadline."""
        return self._cleanup_timeout_seconds

    @property
    def state(self) -> CapabilityLifecycleState:
        """Return the current deterministic coordinator state."""
        return self._state

    async def startup(self) -> None:
        """Start participating capabilities in registry order with rollback."""
        self._require_state(
            CapabilityLifecycleState.INITIALIZED,
            operation=CapabilityLifecyclePhase.STARTUP,
        )
        self._state = CapabilityLifecycleState.STARTING

        for registration in self._registrations:
            started_at = perf_counter()
            self._log_started(registration.name, CapabilityLifecyclePhase.STARTUP)
            try:
                await registration.capability.startup()
            except asyncio.CancelledError as error:
                self._log_cancelled(
                    registration.name,
                    CapabilityLifecyclePhase.STARTUP,
                    started_at=started_at,
                )
                self._state = CapabilityLifecycleState.ROLLING_BACK
                _, cleanup_cancellation = await self._cleanup_started(
                    CapabilityLifecyclePhase.ROLLBACK
                )
                self._state = CapabilityLifecycleState.FAILED
                if cleanup_cancellation is not None:
                    raise cleanup_cancellation from error
                raise
            except Exception as error:
                failure = self._failure(
                    registration.name,
                    CapabilityLifecyclePhase.STARTUP,
                    error=error,
                )
                self._log_failed(failure, started_at=started_at)
                self._state = CapabilityLifecycleState.ROLLING_BACK
                rollback_failures, cleanup_cancellation = await self._cleanup_started(
                    CapabilityLifecyclePhase.ROLLBACK
                )
                self._state = CapabilityLifecycleState.FAILED
                if cleanup_cancellation is not None:
                    raise cleanup_cancellation from error
                raise CapabilityLifecycleError(
                    CapabilityLifecyclePhase.STARTUP,
                    (failure, *rollback_failures),
                ) from error

            self._started.append(registration)
            self._log_completed(
                registration.name,
                CapabilityLifecyclePhase.STARTUP,
                started_at=started_at,
            )

        self._state = CapabilityLifecycleState.STARTED

    async def shutdown(self) -> None:
        """Stop started capabilities in reverse order within bounded deadlines."""
        self._require_state(
            CapabilityLifecycleState.STARTED,
            operation=CapabilityLifecyclePhase.SHUTDOWN,
        )
        self._state = CapabilityLifecycleState.STOPPING
        failures, cancellation = await self._cleanup_started(CapabilityLifecyclePhase.SHUTDOWN)

        if cancellation is not None:
            self._state = CapabilityLifecycleState.FAILED
            raise cancellation
        if failures:
            self._state = CapabilityLifecycleState.FAILED
            raise CapabilityLifecycleError(CapabilityLifecyclePhase.SHUTDOWN, failures)

        self._state = CapabilityLifecycleState.STOPPED

    def _require_state(
        self,
        expected: CapabilityLifecycleState,
        *,
        operation: CapabilityLifecyclePhase,
    ) -> None:
        if self._state is not expected:
            raise CapabilityLifecycleStateError(operation=operation, state=self._state)

    async def _cleanup_started(
        self,
        phase: CapabilityLifecyclePhase,
    ) -> tuple[tuple[CapabilityLifecycleFailure, ...], asyncio.CancelledError | None]:
        failures: list[CapabilityLifecycleFailure] = []
        cancellation: asyncio.CancelledError | None = None

        while self._started:
            registration = self._started.pop()
            started_at = perf_counter()
            self._log_started(registration.name, phase)
            hook_task = asyncio.create_task(
                registration.capability.shutdown(),
                name=f"trussium-capability-{registration.name}-{phase.value}",
            )

            try:
                completed, _ = await asyncio.wait(
                    (hook_task,),
                    timeout=self._cleanup_timeout_seconds,
                )
            except asyncio.CancelledError as error:
                hook_task.cancel()
                hook_task.add_done_callback(self._consume_task_result)
                if cancellation is None:
                    cancellation = error
                self._log_cancelled(registration.name, phase, started_at=started_at)
                continue

            if hook_task not in completed:
                hook_task.cancel()
                hook_task.add_done_callback(self._consume_task_result)
                failure = self._timeout_failure(registration.name, phase)
                failures.append(failure)
                self._log_timeout(failure, started_at=started_at)
                continue

            try:
                hook_task.result()
            except asyncio.CancelledError as error:
                if cancellation is None:
                    cancellation = error
                self._log_cancelled(registration.name, phase, started_at=started_at)
            except Exception as error:
                failure = self._failure(registration.name, phase, error=error)
                failures.append(failure)
                self._log_failed(failure, started_at=started_at)
            else:
                self._log_completed(registration.name, phase, started_at=started_at)

        return tuple(failures), cancellation

    @staticmethod
    def _consume_task_result(task: asyncio.Task[None]) -> None:
        if not task.cancelled():
            task.exception()

    @staticmethod
    def _event(phase: CapabilityLifecyclePhase, outcome: str) -> str:
        events = {
            (CapabilityLifecyclePhase.STARTUP, "started"): CAPABILITY_STARTUP_STARTED,
            (CapabilityLifecyclePhase.STARTUP, "completed"): CAPABILITY_STARTUP_COMPLETED,
            (CapabilityLifecyclePhase.STARTUP, "failed"): CAPABILITY_STARTUP_FAILED,
            (CapabilityLifecyclePhase.STARTUP, "cancelled"): CAPABILITY_STARTUP_CANCELLED,
            (CapabilityLifecyclePhase.ROLLBACK, "started"): CAPABILITY_ROLLBACK_STARTED,
            (CapabilityLifecyclePhase.ROLLBACK, "completed"): CAPABILITY_ROLLBACK_COMPLETED,
            (CapabilityLifecyclePhase.ROLLBACK, "failed"): CAPABILITY_ROLLBACK_FAILED,
            (CapabilityLifecyclePhase.ROLLBACK, "timeout"): CAPABILITY_ROLLBACK_TIMEOUT,
            (CapabilityLifecyclePhase.ROLLBACK, "cancelled"): CAPABILITY_ROLLBACK_CANCELLED,
            (CapabilityLifecyclePhase.SHUTDOWN, "started"): CAPABILITY_SHUTDOWN_STARTED,
            (CapabilityLifecyclePhase.SHUTDOWN, "completed"): CAPABILITY_SHUTDOWN_COMPLETED,
            (CapabilityLifecyclePhase.SHUTDOWN, "failed"): CAPABILITY_SHUTDOWN_FAILED,
            (CapabilityLifecyclePhase.SHUTDOWN, "timeout"): CAPABILITY_SHUTDOWN_TIMEOUT,
            (CapabilityLifecyclePhase.SHUTDOWN, "cancelled"): CAPABILITY_SHUTDOWN_CANCELLED,
        }
        return events[(phase, outcome)]

    @staticmethod
    def _failure_code(phase: CapabilityLifecyclePhase) -> str:
        return f"capability_{phase.value}_failed"

    def _failure(
        self,
        capability_name: str,
        phase: CapabilityLifecyclePhase,
        *,
        error: Exception,
    ) -> CapabilityLifecycleFailure:
        return CapabilityLifecycleFailure(
            capability_name=capability_name,
            phase=phase,
            code=self._failure_code(phase),
            error_type=type(error).__name__,
        )

    @staticmethod
    def _timeout_failure(
        capability_name: str,
        phase: CapabilityLifecyclePhase,
    ) -> CapabilityLifecycleFailure:
        return CapabilityLifecycleFailure(
            capability_name=capability_name,
            phase=phase,
            code=f"capability_{phase.value}_timeout",
            error_type="TimeoutError",
        )

    def _log_started(self, capability_name: str, phase: CapabilityLifecyclePhase) -> None:
        self._logger.info(
            "Capability lifecycle hook started",
            extra={
                "event": self._event(phase, "started"),
                "capability": capability_name,
                "lifecycle_phase": phase.value,
                "cleanup_timeout_seconds": self._cleanup_timeout_seconds,
            },
        )

    def _log_completed(
        self,
        capability_name: str,
        phase: CapabilityLifecyclePhase,
        *,
        started_at: float,
    ) -> None:
        self._logger.info(
            "Capability lifecycle hook completed",
            extra={
                "event": self._event(phase, "completed"),
                "capability": capability_name,
                "lifecycle_phase": phase.value,
                "duration_ms": round((perf_counter() - started_at) * 1000, 3),
                "outcome": "completed",
            },
        )

    def _log_failed(
        self,
        failure: CapabilityLifecycleFailure,
        *,
        started_at: float,
    ) -> None:
        self._logger.error(
            "Capability lifecycle hook failed",
            extra={
                "event": self._event(failure.phase, "failed"),
                "capability": failure.capability_name,
                "lifecycle_phase": failure.phase.value,
                "duration_ms": round((perf_counter() - started_at) * 1000, 3),
                "error_code": failure.code,
                "error_type": failure.error_type,
                "outcome": "failed",
            },
        )

    def _log_timeout(
        self,
        failure: CapabilityLifecycleFailure,
        *,
        started_at: float,
    ) -> None:
        self._logger.error(
            "Capability lifecycle cleanup timed out",
            extra={
                "event": self._event(failure.phase, "timeout"),
                "capability": failure.capability_name,
                "lifecycle_phase": failure.phase.value,
                "duration_ms": round((perf_counter() - started_at) * 1000, 3),
                "cleanup_timeout_seconds": self._cleanup_timeout_seconds,
                "error_code": failure.code,
                "error_type": failure.error_type,
                "outcome": "timed_out",
            },
        )

    def _log_cancelled(
        self,
        capability_name: str,
        phase: CapabilityLifecyclePhase,
        *,
        started_at: float,
    ) -> None:
        self._logger.warning(
            "Capability lifecycle hook cancelled",
            extra={
                "event": self._event(phase, "cancelled"),
                "capability": capability_name,
                "lifecycle_phase": phase.value,
                "duration_ms": round((perf_counter() - started_at) * 1000, 3),
                "error_code": f"capability_{phase.value}_cancelled",
                "error_type": "CancelledError",
                "outcome": "cancelled",
            },
        )


__all__ = [
    "CapabilityLifecycle",
    "CapabilityLifecycleError",
    "CapabilityLifecycleFailure",
    "CapabilityLifecyclePhase",
    "CapabilityLifecycleRegistration",
    "CapabilityLifecycleState",
    "CapabilityLifecycleStateError",
    "LifecycleCapability",
]
