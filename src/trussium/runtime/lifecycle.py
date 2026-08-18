"""Deterministic lifecycle hooks for runtime services."""

import asyncio
import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from time import perf_counter
from typing import Final, Protocol

from trussium.errors import LifecycleError
from trussium.observability.logging import get_logger
from trussium.observability.operations import (
    RUNTIME_SERVICE_ROLLBACK_CANCELLED,
    RUNTIME_SERVICE_ROLLBACK_COMPLETED,
    RUNTIME_SERVICE_ROLLBACK_FAILED,
    RUNTIME_SERVICE_ROLLBACK_STARTED,
    RUNTIME_SERVICE_ROLLBACK_TIMEOUT,
    RUNTIME_SERVICE_SHUTDOWN_CANCELLED,
    RUNTIME_SERVICE_SHUTDOWN_COMPLETED,
    RUNTIME_SERVICE_SHUTDOWN_FAILED,
    RUNTIME_SERVICE_SHUTDOWN_STARTED,
    RUNTIME_SERVICE_SHUTDOWN_TIMEOUT,
    RUNTIME_SERVICE_STARTUP_CANCELLED,
    RUNTIME_SERVICE_STARTUP_COMPLETED,
    RUNTIME_SERVICE_STARTUP_FAILED,
    RUNTIME_SERVICE_STARTUP_STARTED,
)

_SERVICE_NAME_PATTERN: Final = re.compile(r"[a-z][a-z0-9_.-]{0,63}")


def validate_runtime_service_name(name: str) -> str:
    """Return a runtime-service name after validating the public contract."""
    if _SERVICE_NAME_PATTERN.fullmatch(name) is None:
        raise ValueError("Runtime service names must match [a-z][a-z0-9_.-]{0,63}")

    return name


class RuntimeService(Protocol):
    """Asynchronous startup and shutdown contract for one runtime service."""

    @property
    def name(self) -> str:
        """Return the stable, bounded service name used for operations."""
        ...

    async def startup(self) -> None:
        """Initialize the service before the runtime accepts requests."""
        ...

    async def shutdown(self) -> None:
        """Release service resources after active requests have drained."""
        ...


class RuntimeServiceLifecycleState(StrEnum):
    """Deterministic states for the runtime-service lifecycle coordinator."""

    INITIALIZED = "initialized"
    STARTING = "starting"
    STARTED = "started"
    ROLLING_BACK = "rolling_back"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class RuntimeServiceLifecyclePhase(StrEnum):
    """Lifecycle phases exposed by failures and operational events."""

    STARTUP = "startup"
    ROLLBACK = "rollback"
    SHUTDOWN = "shutdown"


@dataclass(frozen=True, slots=True)
class RuntimeServiceFailure:
    """Bounded description of one failed runtime-service hook."""

    service_name: str
    phase: RuntimeServiceLifecyclePhase
    code: str
    error_type: str


class RuntimeServiceLifecycleError(LifecycleError):
    """Aggregate failure raised after all eligible lifecycle hooks run."""

    def __init__(
        self,
        phase: RuntimeServiceLifecyclePhase,
        failures: Sequence[RuntimeServiceFailure],
    ) -> None:
        """Initialize a bounded lifecycle failure without raw exception text."""
        resolved_failures = tuple(failures)
        if not resolved_failures:
            raise ValueError("Lifecycle failures must not be empty")

        super().__init__(
            f"Runtime service {phase.value} failed for {len(resolved_failures)} service(s).",
            code=f"runtime_service_{phase.value}_failed",
        )
        self.phase = phase
        self.failures = resolved_failures


class RuntimeServiceStateError(LifecycleError):
    """Invalid coordinator transition that never re-runs lifecycle hooks."""

    default_code = "runtime_service_state_invalid"

    def __init__(
        self,
        *,
        operation: RuntimeServiceLifecyclePhase,
        state: RuntimeServiceLifecycleState,
    ) -> None:
        """Initialize an invalid transition error with bounded state metadata."""
        super().__init__(f"Runtime service {operation.value} is invalid from state {state.value}.")
        self.operation = operation
        self.state = state


class RuntimeServiceLifecycle:
    """Run ordered runtime-service hooks with rollback and bounded cleanup."""

    def __init__(
        self,
        services: Sequence[RuntimeService] = (),
        *,
        cleanup_timeout_seconds: float = 10.0,
    ) -> None:
        """Create an immutable lifecycle plan for the supplied services."""
        if not isfinite(cleanup_timeout_seconds) or cleanup_timeout_seconds <= 0:
            raise ValueError("Cleanup timeout must be finite and positive")

        resolved_services = tuple(services)
        service_names = tuple(service.name for service in resolved_services)

        for service_name in service_names:
            validate_runtime_service_name(service_name)

        if len(set(service_names)) != len(service_names):
            raise ValueError("Runtime service names must be unique")

        self._services = resolved_services
        self._cleanup_timeout_seconds = cleanup_timeout_seconds
        self._state = RuntimeServiceLifecycleState.INITIALIZED
        self._started_services: list[RuntimeService] = []
        self._logger = get_logger("runtime.lifecycle")

    @property
    def services(self) -> tuple[RuntimeService, ...]:
        """Return the immutable ordered service plan."""
        return self._services

    @property
    def cleanup_timeout_seconds(self) -> float:
        """Return the per-service cleanup deadline."""
        return self._cleanup_timeout_seconds

    @property
    def state(self) -> RuntimeServiceLifecycleState:
        """Return the current deterministic coordinator state."""
        return self._state

    async def startup(self) -> None:
        """Start services in declaration order and roll back partial startup."""
        self._require_state(
            RuntimeServiceLifecycleState.INITIALIZED,
            operation=RuntimeServiceLifecyclePhase.STARTUP,
        )
        self._state = RuntimeServiceLifecycleState.STARTING

        for service in self._services:
            started_at = perf_counter()
            self._log_started(service.name, RuntimeServiceLifecyclePhase.STARTUP)

            try:
                await service.startup()
            except asyncio.CancelledError as error:
                self._log_cancelled(
                    service.name,
                    RuntimeServiceLifecyclePhase.STARTUP,
                    started_at=started_at,
                )
                self._state = RuntimeServiceLifecycleState.ROLLING_BACK
                _, cleanup_cancellation = await self._cleanup_started_services(
                    RuntimeServiceLifecyclePhase.ROLLBACK
                )
                self._state = RuntimeServiceLifecycleState.FAILED
                if cleanup_cancellation is not None:
                    raise cleanup_cancellation from error
                raise
            except Exception as error:
                failure = self._failure(
                    service.name,
                    RuntimeServiceLifecyclePhase.STARTUP,
                    error=error,
                )
                self._log_failed(failure, started_at=started_at)
                self._state = RuntimeServiceLifecycleState.ROLLING_BACK
                rollback_failures, cleanup_cancellation = await self._cleanup_started_services(
                    RuntimeServiceLifecyclePhase.ROLLBACK
                )
                self._state = RuntimeServiceLifecycleState.FAILED
                if cleanup_cancellation is not None:
                    raise cleanup_cancellation from error
                raise RuntimeServiceLifecycleError(
                    RuntimeServiceLifecyclePhase.STARTUP,
                    (failure, *rollback_failures),
                ) from error

            self._started_services.append(service)
            self._log_completed(
                service.name,
                RuntimeServiceLifecyclePhase.STARTUP,
                started_at=started_at,
            )

        self._state = RuntimeServiceLifecycleState.STARTED

    async def shutdown(self) -> None:
        """Stop started services in reverse order within bounded deadlines."""
        self._require_state(
            RuntimeServiceLifecycleState.STARTED,
            operation=RuntimeServiceLifecyclePhase.SHUTDOWN,
        )
        self._state = RuntimeServiceLifecycleState.STOPPING
        failures, cancellation = await self._cleanup_started_services(
            RuntimeServiceLifecyclePhase.SHUTDOWN
        )

        if cancellation is not None:
            self._state = RuntimeServiceLifecycleState.FAILED
            raise cancellation

        if failures:
            self._state = RuntimeServiceLifecycleState.FAILED
            raise RuntimeServiceLifecycleError(
                RuntimeServiceLifecyclePhase.SHUTDOWN,
                failures,
            )

        self._state = RuntimeServiceLifecycleState.STOPPED

    def _require_state(
        self,
        expected: RuntimeServiceLifecycleState,
        *,
        operation: RuntimeServiceLifecyclePhase,
    ) -> None:
        if self._state is not expected:
            raise RuntimeServiceStateError(
                operation=operation,
                state=self._state,
            )

    async def _cleanup_started_services(
        self,
        phase: RuntimeServiceLifecyclePhase,
    ) -> tuple[tuple[RuntimeServiceFailure, ...], asyncio.CancelledError | None]:
        failures: list[RuntimeServiceFailure] = []
        cancellation: asyncio.CancelledError | None = None

        while self._started_services:
            service = self._started_services.pop()
            started_at = perf_counter()
            self._log_started(service.name, phase)
            hook_task = asyncio.create_task(
                service.shutdown(),
                name=f"trussium-{service.name}-{phase.value}",
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
                self._log_cancelled(service.name, phase, started_at=started_at)
                continue

            if hook_task not in completed:
                hook_task.cancel()
                hook_task.add_done_callback(self._consume_task_result)
                failure = self._timeout_failure(service.name, phase)
                failures.append(failure)
                self._log_timeout(failure, started_at=started_at)
                continue

            try:
                hook_task.result()
            except asyncio.CancelledError as error:
                if cancellation is None:
                    cancellation = error
                self._log_cancelled(service.name, phase, started_at=started_at)
            except Exception as error:
                failure = self._failure(service.name, phase, error=error)
                failures.append(failure)
                self._log_failed(failure, started_at=started_at)
            else:
                self._log_completed(service.name, phase, started_at=started_at)

        return tuple(failures), cancellation

    @staticmethod
    def _consume_task_result(task: asyncio.Task[None]) -> None:
        if not task.cancelled():
            task.exception()

    @staticmethod
    def _event(
        phase: RuntimeServiceLifecyclePhase,
        outcome: str,
    ) -> str:
        events = {
            (RuntimeServiceLifecyclePhase.STARTUP, "started"): (RUNTIME_SERVICE_STARTUP_STARTED),
            (RuntimeServiceLifecyclePhase.STARTUP, "completed"): (
                RUNTIME_SERVICE_STARTUP_COMPLETED
            ),
            (RuntimeServiceLifecyclePhase.STARTUP, "failed"): (RUNTIME_SERVICE_STARTUP_FAILED),
            (RuntimeServiceLifecyclePhase.STARTUP, "cancelled"): (
                RUNTIME_SERVICE_STARTUP_CANCELLED
            ),
            (RuntimeServiceLifecyclePhase.ROLLBACK, "started"): (RUNTIME_SERVICE_ROLLBACK_STARTED),
            (RuntimeServiceLifecyclePhase.ROLLBACK, "completed"): (
                RUNTIME_SERVICE_ROLLBACK_COMPLETED
            ),
            (RuntimeServiceLifecyclePhase.ROLLBACK, "failed"): (RUNTIME_SERVICE_ROLLBACK_FAILED),
            (RuntimeServiceLifecyclePhase.ROLLBACK, "timeout"): (RUNTIME_SERVICE_ROLLBACK_TIMEOUT),
            (RuntimeServiceLifecyclePhase.ROLLBACK, "cancelled"): (
                RUNTIME_SERVICE_ROLLBACK_CANCELLED
            ),
            (RuntimeServiceLifecyclePhase.SHUTDOWN, "started"): (RUNTIME_SERVICE_SHUTDOWN_STARTED),
            (RuntimeServiceLifecyclePhase.SHUTDOWN, "completed"): (
                RUNTIME_SERVICE_SHUTDOWN_COMPLETED
            ),
            (RuntimeServiceLifecyclePhase.SHUTDOWN, "failed"): (RUNTIME_SERVICE_SHUTDOWN_FAILED),
            (RuntimeServiceLifecyclePhase.SHUTDOWN, "timeout"): (RUNTIME_SERVICE_SHUTDOWN_TIMEOUT),
            (RuntimeServiceLifecyclePhase.SHUTDOWN, "cancelled"): (
                RUNTIME_SERVICE_SHUTDOWN_CANCELLED
            ),
        }
        return events[(phase, outcome)]

    @staticmethod
    def _failure_code(phase: RuntimeServiceLifecyclePhase) -> str:
        return f"runtime_service_{phase.value}_failed"

    def _failure(
        self,
        service_name: str,
        phase: RuntimeServiceLifecyclePhase,
        *,
        error: Exception,
    ) -> RuntimeServiceFailure:
        return RuntimeServiceFailure(
            service_name=service_name,
            phase=phase,
            code=self._failure_code(phase),
            error_type=type(error).__name__,
        )

    @staticmethod
    def _timeout_failure(
        service_name: str,
        phase: RuntimeServiceLifecyclePhase,
    ) -> RuntimeServiceFailure:
        return RuntimeServiceFailure(
            service_name=service_name,
            phase=phase,
            code=f"runtime_service_{phase.value}_timeout",
            error_type="TimeoutError",
        )

    def _log_started(
        self,
        service_name: str,
        phase: RuntimeServiceLifecyclePhase,
    ) -> None:
        self._logger.info(
            "Runtime service lifecycle hook started",
            extra={
                "event": self._event(phase, "started"),
                "runtime_service": service_name,
                "lifecycle_phase": phase.value,
                "cleanup_timeout_seconds": self._cleanup_timeout_seconds,
            },
        )

    def _log_completed(
        self,
        service_name: str,
        phase: RuntimeServiceLifecyclePhase,
        *,
        started_at: float,
    ) -> None:
        self._logger.info(
            "Runtime service lifecycle hook completed",
            extra={
                "event": self._event(phase, "completed"),
                "runtime_service": service_name,
                "lifecycle_phase": phase.value,
                "duration_ms": round((perf_counter() - started_at) * 1000, 3),
                "outcome": "completed",
            },
        )

    def _log_failed(
        self,
        failure: RuntimeServiceFailure,
        *,
        started_at: float,
    ) -> None:
        self._logger.error(
            "Runtime service lifecycle hook failed",
            extra={
                "event": self._event(failure.phase, "failed"),
                "runtime_service": failure.service_name,
                "lifecycle_phase": failure.phase.value,
                "duration_ms": round((perf_counter() - started_at) * 1000, 3),
                "error_code": failure.code,
                "error_type": failure.error_type,
                "outcome": "failed",
            },
        )

    def _log_timeout(
        self,
        failure: RuntimeServiceFailure,
        *,
        started_at: float,
    ) -> None:
        self._logger.error(
            "Runtime service lifecycle cleanup timed out",
            extra={
                "event": self._event(failure.phase, "timeout"),
                "runtime_service": failure.service_name,
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
        service_name: str,
        phase: RuntimeServiceLifecyclePhase,
        *,
        started_at: float,
    ) -> None:
        self._logger.warning(
            "Runtime service lifecycle hook cancelled",
            extra={
                "event": self._event(phase, "cancelled"),
                "runtime_service": service_name,
                "lifecycle_phase": phase.value,
                "duration_ms": round((perf_counter() - started_at) * 1000, 3),
                "error_code": f"runtime_service_{phase.value}_cancelled",
                "error_type": "CancelledError",
                "outcome": "cancelled",
            },
        )


__all__ = [
    "RuntimeService",
    "RuntimeServiceFailure",
    "RuntimeServiceLifecycle",
    "RuntimeServiceLifecycleError",
    "RuntimeServiceLifecyclePhase",
    "RuntimeServiceLifecycleState",
    "RuntimeServiceStateError",
]
