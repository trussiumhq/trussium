"""Deterministic availability reporting for registered capabilities."""

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

CAPABILITY_AVAILABILITY_TIMEOUT: Final = "capability_availability_timeout"
CAPABILITY_AVAILABILITY_CHECK_FAILED: Final = "capability_availability_check_failed"

_REASON_PATTERN: Final = re.compile(r"[a-z][a-z0-9_]{0,63}")


class CapabilityAvailabilityStatus(StrEnum):
    """Bounded availability states for provider-neutral capabilities."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class CapabilityAvailability:
    """Immutable bounded availability for one registered capability."""

    name: str
    status: CapabilityAvailabilityStatus
    reason: str | None = None

    def __post_init__(self) -> None:
        """Validate capability identity and status-dependent reason semantics."""
        validate_capability_name(self.name)

        if not isinstance(self.status, CapabilityAvailabilityStatus):
            raise ValueError(
                "Capability availability status must be a CapabilityAvailabilityStatus"
            )

        if self.status is CapabilityAvailabilityStatus.AVAILABLE:
            if self.reason is not None:
                raise ValueError("Available capabilities must not include a reason")
            return

        if self.reason is None or _REASON_PATTERN.fullmatch(self.reason) is None:
            raise ValueError("Unavailable capability reasons must match [a-z][a-z0-9_]{0,63}")


@runtime_checkable
class CapabilityAvailabilityCheck(Protocol):
    """Optional asynchronous availability contract for a registered capability."""

    async def check_availability(self) -> CapabilityAvailability:
        """Return the capability's current bounded availability."""
        ...


@dataclass(frozen=True, slots=True)
class CapabilityAvailabilityReport:
    """Immutable aggregate over capabilities in stable registration order."""

    status: CapabilityAvailabilityStatus
    capabilities: tuple[CapabilityAvailability, ...]


@dataclass(frozen=True, slots=True)
class _CapabilityEvaluation:
    availability: CapabilityAvailability
    duration_ms: float
    error_type: str | None = None


class CapabilityAvailabilityReporter:
    """Evaluate capability availability concurrently and aggregate deterministically."""

    def __init__(
        self,
        registry: CapabilityRegistry,
        *,
        timeout_seconds: float = 1.0,
    ) -> None:
        """Bind reporting to one sealed registry and positive finite deadline."""
        if not registry.sealed:
            raise ValueError("Capability availability reporting requires a sealed registry")
        if not isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("Capability availability timeout must be finite and positive")

        self._registry = registry
        self._timeout_seconds = timeout_seconds
        self._lock = asyncio.Lock()
        self._logged_states: dict[str, tuple[CapabilityAvailabilityStatus, str | None]] = {}
        self._logger = get_logger("capability.availability")

    @property
    def registry(self) -> CapabilityRegistry:
        """Return the sealed registry that owns reported capabilities."""
        return self._registry

    @property
    def timeout_seconds(self) -> float:
        """Return the per-capability reporting deadline."""
        return self._timeout_seconds

    async def report(self) -> CapabilityAvailabilityReport:
        """Return one fresh ordered report while serializing concurrent callers."""
        async with self._lock:
            registrations = self._registry.registrations
            evaluations = await asyncio.gather(
                *(
                    self._evaluate(registration.name, registration.capability)
                    for registration in registrations
                )
            )
            capabilities = tuple(evaluation.availability for evaluation in evaluations)

            for evaluation in evaluations:
                self._log_transition(evaluation)

            status = (
                CapabilityAvailabilityStatus.UNAVAILABLE
                if any(
                    capability.status is CapabilityAvailabilityStatus.UNAVAILABLE
                    for capability in capabilities
                )
                else CapabilityAvailabilityStatus.AVAILABLE
            )
            return CapabilityAvailabilityReport(status=status, capabilities=capabilities)

    async def _evaluate(self, name: str, capability: object) -> _CapabilityEvaluation:
        started_at = perf_counter()
        if not isinstance(capability, CapabilityAvailabilityCheck):
            return self._evaluation(
                CapabilityAvailability(name=name, status=CapabilityAvailabilityStatus.AVAILABLE),
                started_at=started_at,
            )

        try:
            availability = await self._check_with_timeout(capability.check_availability())
        except TimeoutError:
            return self._failed_evaluation(
                name,
                reason=CAPABILITY_AVAILABILITY_TIMEOUT,
                error_type="TimeoutError",
                started_at=started_at,
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            return self._failed_evaluation(
                name,
                reason=CAPABILITY_AVAILABILITY_CHECK_FAILED,
                error_type=type(error).__name__,
                started_at=started_at,
            )

        if not isinstance(availability, CapabilityAvailability) or availability.name != name:
            return self._failed_evaluation(
                name,
                reason=CAPABILITY_AVAILABILITY_CHECK_FAILED,
                error_type=(
                    "TypeError"
                    if not isinstance(availability, CapabilityAvailability)
                    else "ValueError"
                ),
                started_at=started_at,
            )

        return self._evaluation(availability, started_at=started_at)

    async def _check_with_timeout(
        self,
        check: Awaitable[CapabilityAvailability],
    ) -> CapabilityAvailability:
        async with asyncio.timeout(self._timeout_seconds):
            return await check

    def _failed_evaluation(
        self,
        name: str,
        *,
        reason: str,
        error_type: str,
        started_at: float,
    ) -> _CapabilityEvaluation:
        return self._evaluation(
            CapabilityAvailability(
                name=name,
                status=CapabilityAvailabilityStatus.UNAVAILABLE,
                reason=reason,
            ),
            started_at=started_at,
            error_type=error_type,
        )

    @staticmethod
    def _evaluation(
        availability: CapabilityAvailability,
        *,
        started_at: float,
        error_type: str | None = None,
    ) -> _CapabilityEvaluation:
        return _CapabilityEvaluation(
            availability=availability,
            duration_ms=round((perf_counter() - started_at) * 1000, 3),
            error_type=error_type,
        )

    def _log_transition(self, evaluation: _CapabilityEvaluation) -> None:
        availability = evaluation.availability
        state = (availability.status, availability.reason)
        if self._logged_states.get(availability.name) == state:
            return

        self._logged_states[availability.name] = state
        extra: dict[str, object] = {
            "event": f"capability.availability.{availability.status.value}",
            "capability": availability.name,
            "outcome": availability.status.value,
            "duration_ms": evaluation.duration_ms,
        }
        if availability.reason is not None:
            extra["error_code"] = availability.reason
        if evaluation.error_type is not None:
            extra["error_type"] = evaluation.error_type

        log = (
            self._logger.warning
            if availability.status is CapabilityAvailabilityStatus.UNAVAILABLE
            else self._logger.info
        )
        log("Capability availability changed", extra=extra)


__all__ = [
    "CAPABILITY_AVAILABILITY_CHECK_FAILED",
    "CAPABILITY_AVAILABILITY_TIMEOUT",
    "CapabilityAvailability",
    "CapabilityAvailabilityCheck",
    "CapabilityAvailabilityReport",
    "CapabilityAvailabilityReporter",
    "CapabilityAvailabilityStatus",
]
