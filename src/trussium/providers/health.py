"""Informational health reporting for registered providers."""

import asyncio
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import ClassVar, Protocol, runtime_checkable

from trussium.observability.logging import get_logger
from trussium.providers.registry import ProviderRegistry


class ProviderHealthStatus(StrEnum):
    """Bounded provider health states."""

    OK = "ok"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    """Immutable bounded health state for one provider."""

    name: str
    status: ProviderHealthStatus
    reason: str | None = None


@runtime_checkable
class ProviderHealthCheck(Protocol):
    """Optional asynchronous provider health contract."""

    async def check_health(self) -> ProviderHealth:
        """Return the provider's current bounded health state."""
        ...


@dataclass(frozen=True, slots=True)
class ProviderHealthReport:
    """Immutable ordered aggregate over registered providers."""

    status: ProviderHealthStatus
    providers: tuple[ProviderHealth, ...]


class ProviderHealthReporter:
    """Evaluate provider health concurrently without affecting readiness."""

    _PRECEDENCE: ClassVar[dict[ProviderHealthStatus, int]] = {
        ProviderHealthStatus.OK: 0,
        ProviderHealthStatus.UNKNOWN: 1,
        ProviderHealthStatus.DEGRADED: 2,
        ProviderHealthStatus.UNAVAILABLE: 3,
    }

    def __init__(self, registry: ProviderRegistry, *, timeout_seconds: float = 1.0) -> None:
        if not registry.sealed:
            raise ValueError("Provider health reporting requires a sealed registry")
        if not isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("Provider health timeout must be finite and positive")
        self._registry = registry
        self._timeout_seconds = timeout_seconds
        self._lock = asyncio.Lock()
        self._logger = get_logger("provider.health")

    @property
    def registry(self) -> ProviderRegistry:
        """Return the sealed provider registry."""
        return self._registry

    @property
    def timeout_seconds(self) -> float:
        """Return the per-provider deadline."""
        return self._timeout_seconds

    async def report(self) -> ProviderHealthReport:
        """Return a fresh, ordered provider health report."""
        async with self._lock:
            providers = tuple(
                await asyncio.gather(
                    *(
                        self._evaluate(provider.metadata.name, provider)
                        for provider in self._registry
                    )
                )
            )
            return ProviderHealthReport(self._aggregate(providers), providers)

    async def _evaluate(self, name: str, provider: object) -> ProviderHealth:
        if not isinstance(provider, ProviderHealthCheck):
            return ProviderHealth(name, ProviderHealthStatus.UNKNOWN, "health_not_reported")
        try:
            async with asyncio.timeout(self._timeout_seconds):
                health = await provider.check_health()
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            return ProviderHealth(name, ProviderHealthStatus.UNAVAILABLE, "health_timeout")
        except Exception as error:
            self._logger.warning(
                "Provider health check failed",
                extra={"provider": name, "error_type": type(error).__name__},
            )
            return ProviderHealth(name, ProviderHealthStatus.UNAVAILABLE, "health_check_failed")
        if not isinstance(health, ProviderHealth) or health.name != name:
            return ProviderHealth(name, ProviderHealthStatus.UNAVAILABLE, "health_check_failed")
        return health

    def _aggregate(self, providers: tuple[ProviderHealth, ...]) -> ProviderHealthStatus:
        if not providers:
            return ProviderHealthStatus.OK
        return max((item.status for item in providers), key=self._PRECEDENCE.__getitem__)


__all__ = [
    "ProviderHealth",
    "ProviderHealthCheck",
    "ProviderHealthReport",
    "ProviderHealthReporter",
    "ProviderHealthStatus",
]
