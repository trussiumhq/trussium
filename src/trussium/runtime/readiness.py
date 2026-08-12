"""Provider-neutral dependency readiness contracts and evaluation."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from time import monotonic
from typing import Protocol, runtime_checkable

from trussium.observability.logging import get_logger


class DependencyStatus(StrEnum):
    """Bounded dependency readiness states."""

    OK = "ok"
    UNAVAILABLE = "unavailable"


class DependencyFailureReason(StrEnum):
    """Stable provider dependency failure reasons."""

    PROVIDER_NOT_CONFIGURED = "provider_not_configured"
    PROVIDER_AUTHENTICATION_FAILED = "provider_authentication_failed"
    PROVIDER_PERMISSION_DENIED = "provider_permission_denied"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_UNREACHABLE = "provider_unreachable"
    MODEL_UNAVAILABLE = "model_unavailable"
    PROVIDER_CHECK_FAILED = "provider_check_failed"


@dataclass(frozen=True, slots=True)
class DependencyHealth:
    """Immutable bounded result of one dependency check."""

    name: str
    status: DependencyStatus
    provider: str
    model: str | None = None
    reason: DependencyFailureReason | None = None


@runtime_checkable
class DependencyHealthCheck(Protocol):
    """Asynchronously validate and close one external dependency."""

    @property
    def name(self) -> str:
        """Return the stable dependency name."""
        ...

    @property
    def provider(self) -> str:
        """Return the bounded provider identifier."""
        ...

    @property
    def model(self) -> str | None:
        """Return the optional configured required model."""
        ...

    async def check(self) -> DependencyHealth:
        """Return the current bounded dependency state."""
        ...

    async def close(self) -> None:
        """Close resources owned by the check."""
        ...


class UnavailableDependencyHealthCheck:
    """Report a statically unavailable configured dependency."""

    name = "provider"

    def __init__(
        self,
        *,
        provider: str,
        model: str | None,
        reason: DependencyFailureReason,
    ) -> None:
        """Initialize a bounded unavailable result."""
        self._provider = provider
        self._model = model
        self._reason = reason

    @property
    def provider(self) -> str:
        """Return the configured provider name."""
        return self._provider

    @property
    def model(self) -> str | None:
        """Return the optional required model."""
        return self._model

    async def check(self) -> DependencyHealth:
        """Return the static unavailable state."""
        return DependencyHealth(
            name=self.name,
            status=DependencyStatus.UNAVAILABLE,
            provider=self.provider,
            model=self.model,
            reason=self._reason,
        )

    async def close(self) -> None:
        """Close no resources."""


class DependencyReadiness:
    """Evaluate a dependency with a bounded single-flight cache."""

    def __init__(
        self,
        check: DependencyHealthCheck,
        *,
        timeout_seconds: float,
        cache_seconds: float,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        """Initialize dependency evaluation settings and state."""
        self._check = check
        self._timeout_seconds = timeout_seconds
        self._cache_seconds = cache_seconds
        self._clock = clock
        self._lock = asyncio.Lock()
        self._cached_at: float | None = None
        self._cached_result: DependencyHealth | None = None
        self._logged_state: tuple[DependencyStatus, DependencyFailureReason | None] | None = None
        self._logger = get_logger("readiness")

    async def evaluate(self) -> DependencyHealth:
        """Return a fresh or still-valid cached dependency result."""
        cached = self._valid_cached_result()

        if cached is not None:
            return cached

        async with self._lock:
            cached = self._valid_cached_result()

            if cached is not None:
                return cached

            result = await self._refresh()
            self._cached_at = self._clock()
            self._cached_result = result
            self._log_transition(result)
            return result

    async def close(self) -> None:
        """Close resources owned by the underlying dependency check."""
        await self._check.close()

    def _valid_cached_result(self) -> DependencyHealth | None:
        """Return a cached result only while its monotonic TTL is valid."""
        if self._cached_at is None or self._cached_result is None:
            return None

        if self._clock() - self._cached_at >= self._cache_seconds:
            return None

        return self._cached_result

    async def _refresh(self) -> DependencyHealth:
        """Run one dependency refresh within the runtime-owned deadline."""
        try:
            async with asyncio.timeout(self._timeout_seconds):
                return await self._check.check()
        except TimeoutError:
            return self._unavailable(DependencyFailureReason.PROVIDER_TIMEOUT)
        except asyncio.CancelledError:
            raise
        except Exception:
            return self._unavailable(DependencyFailureReason.PROVIDER_CHECK_FAILED)

    def _unavailable(self, reason: DependencyFailureReason) -> DependencyHealth:
        """Build a bounded unavailable result without raw failure data."""
        return DependencyHealth(
            name=self._check.name,
            status=DependencyStatus.UNAVAILABLE,
            provider=self._check.provider,
            model=self._check.model,
            reason=reason,
        )

    def _log_transition(self, result: DependencyHealth) -> None:
        """Log only dependency state transitions with bounded fields."""
        state = (result.status, result.reason)

        if state == self._logged_state:
            return

        self._logged_state = state
        extra: dict[str, object] = {
            "event": f"readiness.dependency.{result.status}",
            "outcome": result.status,
            "provider": result.provider,
        }

        if result.model is not None:
            extra["model"] = result.model

        if result.reason is not None:
            extra["error_code"] = result.reason

        log = self._logger.info if result.status is DependencyStatus.OK else self._logger.warning
        log("Readiness dependency state changed", extra=extra)
