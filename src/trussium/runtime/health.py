"""Deterministic health reporting for registered runtime services."""

import asyncio
import re
from collections.abc import Awaitable
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from time import perf_counter
from typing import Final, Protocol, runtime_checkable

from trussium.observability.logging import get_logger
from trussium.runtime.lifecycle import RuntimeService, validate_runtime_service_name
from trussium.runtime.registry import RuntimeServiceRegistry

COMPONENT_HEALTH_NOT_REPORTED: Final = "component_health_not_reported"
COMPONENT_HEALTH_TIMEOUT: Final = "component_health_timeout"
COMPONENT_HEALTH_CHECK_FAILED: Final = "component_health_check_failed"

_REASON_PATTERN: Final = re.compile(r"[a-z][a-z0-9_]{0,63}")


class RuntimeComponentStatus(StrEnum):
    """Bounded health states reported by application-scoped components."""

    OK = "ok"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RuntimeComponentHealth:
    """Immutable bounded health state for one registered runtime service."""

    name: str
    status: RuntimeComponentStatus
    reason: str | None = None

    def __post_init__(self) -> None:
        """Validate service identity and reason semantics at construction."""
        validate_runtime_service_name(self.name)

        if not isinstance(self.status, RuntimeComponentStatus):
            raise ValueError("Runtime component health status must be a RuntimeComponentStatus")

        if self.status is RuntimeComponentStatus.OK:
            if self.reason is not None:
                raise ValueError("Healthy runtime components must not include a reason")
            return

        if self.reason is None or _REASON_PATTERN.fullmatch(self.reason) is None:
            raise ValueError(
                "Non-healthy runtime component reasons must match [a-z][a-z0-9_]{0,63}"
            )


@runtime_checkable
class RuntimeComponentHealthCheck(Protocol):
    """Optional asynchronous health contract for one registered service."""

    async def check_health(self) -> RuntimeComponentHealth:
        """Return the component's current bounded health state."""
        ...


@dataclass(frozen=True, slots=True)
class RuntimeComponentHealthReport:
    """Immutable aggregate over every service in stable registry order."""

    status: RuntimeComponentStatus
    components: tuple[RuntimeComponentHealth, ...]


@dataclass(frozen=True, slots=True)
class _ComponentEvaluation:
    health: RuntimeComponentHealth
    duration_ms: float
    error_type: str | None = None


class RuntimeComponentHealthReporter:
    """Evaluate component health concurrently and aggregate deterministically."""

    _STATUS_PRECEDENCE: Final[dict[RuntimeComponentStatus, int]] = {
        RuntimeComponentStatus.OK: 0,
        RuntimeComponentStatus.UNKNOWN: 1,
        RuntimeComponentStatus.DEGRADED: 2,
        RuntimeComponentStatus.UNAVAILABLE: 3,
    }

    def __init__(
        self,
        registry: RuntimeServiceRegistry,
        *,
        timeout_seconds: float = 1.0,
    ) -> None:
        """Bind reporting to one sealed registry and positive finite deadline."""
        if not registry.sealed:
            raise ValueError("Runtime component health reporting requires a sealed registry")
        if not isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("Component health timeout must be finite and positive")

        self._registry = registry
        self._timeout_seconds = timeout_seconds
        self._lock = asyncio.Lock()
        self._logged_states: dict[str, tuple[RuntimeComponentStatus, str | None]] = {}
        self._logger = get_logger("runtime.health")

    @property
    def registry(self) -> RuntimeServiceRegistry:
        """Return the sealed registry that owns reported services."""
        return self._registry

    @property
    def timeout_seconds(self) -> float:
        """Return the per-component reporting deadline."""
        return self._timeout_seconds

    async def report(self) -> RuntimeComponentHealthReport:
        """Return one fresh ordered report while serializing concurrent callers."""
        async with self._lock:
            registered_services = tuple(
                zip(self._registry.names, self._registry.services, strict=True)
            )
            evaluations = await asyncio.gather(
                *(
                    self._evaluate(service_name, service)
                    for service_name, service in registered_services
                )
            )
            components = tuple(evaluation.health for evaluation in evaluations)

            for evaluation in evaluations:
                self._log_transition(evaluation)

            return RuntimeComponentHealthReport(
                status=self._aggregate_status(components),
                components=components,
            )

    async def _evaluate(
        self,
        service_name: str,
        service: RuntimeService,
    ) -> _ComponentEvaluation:
        started_at = perf_counter()

        if not isinstance(service, RuntimeComponentHealthCheck):
            return self._evaluation(
                RuntimeComponentHealth(
                    name=service_name,
                    status=RuntimeComponentStatus.UNKNOWN,
                    reason=COMPONENT_HEALTH_NOT_REPORTED,
                ),
                started_at=started_at,
            )

        try:
            health = await self._check_with_timeout(service.check_health())
        except TimeoutError:
            return self._failed_evaluation(
                service_name,
                reason=COMPONENT_HEALTH_TIMEOUT,
                error_type="TimeoutError",
                started_at=started_at,
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            return self._failed_evaluation(
                service_name,
                reason=COMPONENT_HEALTH_CHECK_FAILED,
                error_type=type(error).__name__,
                started_at=started_at,
            )

        if not isinstance(health, RuntimeComponentHealth) or health.name != service_name:
            return self._failed_evaluation(
                service_name,
                reason=COMPONENT_HEALTH_CHECK_FAILED,
                error_type=(
                    "TypeError" if not isinstance(health, RuntimeComponentHealth) else "ValueError"
                ),
                started_at=started_at,
            )

        return self._evaluation(health, started_at=started_at)

    async def _check_with_timeout(
        self,
        check: Awaitable[RuntimeComponentHealth],
    ) -> RuntimeComponentHealth:
        async with asyncio.timeout(self._timeout_seconds):
            return await check

    def _failed_evaluation(
        self,
        service_name: str,
        *,
        reason: str,
        error_type: str,
        started_at: float,
    ) -> _ComponentEvaluation:
        return self._evaluation(
            RuntimeComponentHealth(
                name=service_name,
                status=RuntimeComponentStatus.UNAVAILABLE,
                reason=reason,
            ),
            started_at=started_at,
            error_type=error_type,
        )

    @staticmethod
    def _evaluation(
        health: RuntimeComponentHealth,
        *,
        started_at: float,
        error_type: str | None = None,
    ) -> _ComponentEvaluation:
        return _ComponentEvaluation(
            health=health,
            duration_ms=round((perf_counter() - started_at) * 1000, 3),
            error_type=error_type,
        )

    def _aggregate_status(
        self,
        components: tuple[RuntimeComponentHealth, ...],
    ) -> RuntimeComponentStatus:
        if not components:
            return RuntimeComponentStatus.OK

        return max(
            (component.status for component in components),
            key=self._STATUS_PRECEDENCE.__getitem__,
        )

    def _log_transition(self, evaluation: _ComponentEvaluation) -> None:
        health = evaluation.health
        state = (health.status, health.reason)

        if self._logged_states.get(health.name) == state:
            return

        self._logged_states[health.name] = state
        extra: dict[str, object] = {
            "event": f"runtime.component.health.{health.status.value}",
            "runtime_service": health.name,
            "outcome": health.status.value,
            "duration_ms": evaluation.duration_ms,
        }

        if health.reason is not None:
            extra["error_code"] = health.reason
        if evaluation.error_type is not None:
            extra["error_type"] = evaluation.error_type

        log = (
            self._logger.warning
            if health.status
            in {RuntimeComponentStatus.DEGRADED, RuntimeComponentStatus.UNAVAILABLE}
            else self._logger.info
        )
        log("Runtime component health changed", extra=extra)


__all__ = [
    "COMPONENT_HEALTH_CHECK_FAILED",
    "COMPONENT_HEALTH_NOT_REPORTED",
    "COMPONENT_HEALTH_TIMEOUT",
    "RuntimeComponentHealth",
    "RuntimeComponentHealthCheck",
    "RuntimeComponentHealthReport",
    "RuntimeComponentHealthReporter",
    "RuntimeComponentStatus",
]
