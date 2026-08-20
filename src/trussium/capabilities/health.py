"""Deterministic health reporting for registered capabilities."""

import asyncio
import re
from collections.abc import Awaitable
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from time import perf_counter
from typing import Final, Protocol, runtime_checkable

from trussium.capabilities.registry import CapabilityRegistry, validate_capability_name
from trussium.observability.logging import get_logger

CAPABILITY_HEALTH_NOT_REPORTED: Final = "capability_health_not_reported"
CAPABILITY_HEALTH_TIMEOUT: Final = "capability_health_timeout"
CAPABILITY_HEALTH_CHECK_FAILED: Final = "capability_health_check_failed"

_REASON_PATTERN: Final = re.compile(r"[a-z][a-z0-9_]{0,63}")


class CapabilityHealthStatus(StrEnum):
    """Bounded health states for provider-neutral capabilities."""

    OK = "ok"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CapabilityHealth:
    """Immutable bounded health state for one registered capability."""

    name: str
    status: CapabilityHealthStatus
    reason: str | None = None

    def __post_init__(self) -> None:
        """Validate capability identity and reason semantics."""
        validate_capability_name(self.name)
        if not isinstance(self.status, CapabilityHealthStatus):
            raise ValueError("Capability health status must be a CapabilityHealthStatus")
        if self.status is CapabilityHealthStatus.OK:
            if self.reason is not None:
                raise ValueError("Healthy capabilities must not include a reason")
            return
        if self.reason is None or _REASON_PATTERN.fullmatch(self.reason) is None:
            raise ValueError("Non-healthy capability reasons must match [a-z][a-z0-9_]{0,63}")


@runtime_checkable
class CapabilityHealthCheck(Protocol):
    """Optional asynchronous health contract for a registered capability."""

    async def check_health(self) -> CapabilityHealth:
        """Return the capability's current bounded health state."""
        ...


@dataclass(frozen=True, slots=True)
class CapabilityHealthReport:
    """Immutable aggregate over capabilities in stable registration order."""

    status: CapabilityHealthStatus
    capabilities: tuple[CapabilityHealth, ...]


@dataclass(frozen=True, slots=True)
class _CapabilityEvaluation:
    health: CapabilityHealth
    duration_ms: float
    error_type: str | None = None


class CapabilityHealthReporter:
    """Evaluate capability health concurrently and aggregate deterministically."""

    _STATUS_PRECEDENCE: Final[dict[CapabilityHealthStatus, int]] = {
        CapabilityHealthStatus.OK: 0,
        CapabilityHealthStatus.UNKNOWN: 1,
        CapabilityHealthStatus.DEGRADED: 2,
        CapabilityHealthStatus.UNAVAILABLE: 3,
    }

    def __init__(self, registry: CapabilityRegistry, *, timeout_seconds: float = 1.0) -> None:
        """Bind reporting to one sealed registry and positive finite deadline."""
        if not registry.sealed:
            raise ValueError("Capability health reporting requires a sealed registry")
        if not isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("Capability health timeout must be finite and positive")
        self._registry = registry
        self._timeout_seconds = timeout_seconds
        self._lock = asyncio.Lock()
        self._logged_states: dict[str, tuple[CapabilityHealthStatus, str | None]] = {}
        self._logger = get_logger("capability.health")

    @property
    def registry(self) -> CapabilityRegistry:
        """Return the sealed registry that owns reported capabilities."""
        return self._registry

    @property
    def timeout_seconds(self) -> float:
        """Return the per-capability reporting deadline."""
        return self._timeout_seconds

    async def report(self) -> CapabilityHealthReport:
        """Return one fresh ordered report while serializing concurrent callers."""
        async with self._lock:
            evaluations = await asyncio.gather(
                *(
                    self._evaluate(item.name, item.capability)
                    for item in self._registry.registrations
                )
            )
            capabilities = tuple(evaluation.health for evaluation in evaluations)
            for evaluation in evaluations:
                self._log_transition(evaluation)
            return CapabilityHealthReport(
                status=self._aggregate_status(capabilities), capabilities=capabilities
            )

    async def _evaluate(self, name: str, capability: object) -> _CapabilityEvaluation:
        started_at = perf_counter()
        if not isinstance(capability, CapabilityHealthCheck):
            return self._evaluation(
                CapabilityHealth(
                    name=name,
                    status=CapabilityHealthStatus.UNKNOWN,
                    reason=CAPABILITY_HEALTH_NOT_REPORTED,
                ),
                started_at=started_at,
            )
        try:
            health = await self._check_with_timeout(capability.check_health())
        except TimeoutError:
            return self._failed_evaluation(
                name,
                reason=CAPABILITY_HEALTH_TIMEOUT,
                error_type="TimeoutError",
                started_at=started_at,
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            return self._failed_evaluation(
                name,
                reason=CAPABILITY_HEALTH_CHECK_FAILED,
                error_type=type(error).__name__,
                started_at=started_at,
            )
        if not isinstance(health, CapabilityHealth) or health.name != name:
            return self._failed_evaluation(
                name,
                reason=CAPABILITY_HEALTH_CHECK_FAILED,
                error_type="TypeError"
                if not isinstance(health, CapabilityHealth)
                else "ValueError",
                started_at=started_at,
            )
        return self._evaluation(health, started_at=started_at)

    async def _check_with_timeout(self, check: Awaitable[CapabilityHealth]) -> CapabilityHealth:
        async with asyncio.timeout(self._timeout_seconds):
            return await check

    def _failed_evaluation(
        self, name: str, *, reason: str, error_type: str, started_at: float
    ) -> _CapabilityEvaluation:
        return self._evaluation(
            CapabilityHealth(name=name, status=CapabilityHealthStatus.UNAVAILABLE, reason=reason),
            started_at=started_at,
            error_type=error_type,
        )

    @staticmethod
    def _evaluation(
        health: CapabilityHealth, *, started_at: float, error_type: str | None = None
    ) -> _CapabilityEvaluation:
        return _CapabilityEvaluation(
            health=health,
            duration_ms=round((perf_counter() - started_at) * 1000, 3),
            error_type=error_type,
        )

    def _aggregate_status(
        self, capabilities: tuple[CapabilityHealth, ...]
    ) -> CapabilityHealthStatus:
        if not capabilities:
            return CapabilityHealthStatus.OK
        return max(
            (capability.status for capability in capabilities),
            key=self._STATUS_PRECEDENCE.__getitem__,
        )

    def _log_transition(self, evaluation: _CapabilityEvaluation) -> None:
        health = evaluation.health
        state = (health.status, health.reason)
        if self._logged_states.get(health.name) == state:
            return
        self._logged_states[health.name] = state
        extra: dict[str, object] = {
            "event": f"capability.health.{health.status.value}",
            "capability": health.name,
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
            in {CapabilityHealthStatus.DEGRADED, CapabilityHealthStatus.UNAVAILABLE}
            else self._logger.info
        )
        log("Capability health changed", extra=extra)


__all__ = [
    "CAPABILITY_HEALTH_CHECK_FAILED",
    "CAPABILITY_HEALTH_NOT_REPORTED",
    "CAPABILITY_HEALTH_TIMEOUT",
    "CapabilityHealth",
    "CapabilityHealthCheck",
    "CapabilityHealthReport",
    "CapabilityHealthReporter",
    "CapabilityHealthStatus",
]
