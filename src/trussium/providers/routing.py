"""Deterministic provider-priority selection and fallback."""

from collections.abc import Awaitable, Callable, Sequence

from trussium.providers.circuit_breaker import CircuitBreaker
from trussium.providers.contracts import Provider, validate_provider_name
from trussium.providers.health import ProviderHealthReporter, ProviderHealthStatus
from trussium.providers.registry import ProviderRegistry


class ProviderRouter:
    """Select the first registered provider matching a capability."""

    def __init__(
        self,
        registry: ProviderRegistry,
        priority: Sequence[str] = (),
        circuit_breaker: CircuitBreaker | None = None,
        health_reporter: ProviderHealthReporter | None = None,
    ) -> None:
        if not registry.sealed:
            raise ValueError("Provider routing requires a sealed registry")
        normalized = tuple(validate_provider_name(name) for name in priority)
        if len(normalized) != len(set(normalized)):
            raise ValueError("Provider routing priorities must be unique")
        self._registry = registry
        self._priority = normalized
        self._circuit_breaker = circuit_breaker
        self._health_reporter = health_reporter

    @property
    def priority(self) -> tuple[str, ...]:
        """Return the immutable configured priority order."""
        return self._priority

    def select(self, capability: str) -> Provider | None:
        """Return the highest-priority provider advertising a capability."""
        candidates = self._priority or self._registry.names
        for name in candidates:
            provider = self._registry.get(name)
            if provider is not None and capability in provider.metadata.capabilities:
                return provider
        return None

    def candidates(self, capability: str) -> tuple[Provider, ...]:
        """Return all capability-compatible providers in deterministic order."""
        names = self._priority or self._registry.names
        return tuple(
            provider
            for name in names
            if (provider := self._registry.get(name)) is not None
            and capability in provider.metadata.capabilities
            and (self._circuit_breaker is None or self._circuit_breaker.allow(name))
        )

    async def execute_with_fallback(
        self,
        capability: str,
        operation: Callable[[Provider], Awaitable[object]],
    ) -> object:
        """Execute against ordered providers, falling back on transient failures."""
        from trussium.providers.retry import ProviderFailureClass, classify_failure

        candidates = (
            await self._healthy_candidates(capability)
            if self._health_reporter is not None
            else self.candidates(capability)
        )
        if not candidates:
            raise LookupError(f"No provider advertises capability '{capability}'")
        for index, provider in enumerate(candidates):
            try:
                result = await operation(provider)
                if self._circuit_breaker is not None:
                    self._circuit_breaker.record_success(provider.metadata.name)
                return result
            except BaseException as error:
                if (
                    classify_failure(error)
                    not in {
                        ProviderFailureClass.RATE_LIMITED,
                        ProviderFailureClass.TIMEOUT,
                        ProviderFailureClass.CONNECTION,
                        ProviderFailureClass.UPSTREAM,
                    }
                    or index == len(candidates) - 1
                ):
                    if self._circuit_breaker is not None:
                        self._circuit_breaker.record_failure(provider.metadata.name)
                    raise
                if self._circuit_breaker is not None:
                    self._circuit_breaker.record_failure(provider.metadata.name)
        raise AssertionError("Provider fallback exhausted without a result")

    async def _healthy_candidates(self, capability: str) -> tuple[Provider, ...]:
        assert self._health_reporter is not None
        report = await self._health_reporter.report()
        unavailable = {
            item.name
            for item in report.providers
            if item.status is ProviderHealthStatus.UNAVAILABLE
        }
        return tuple(
            provider
            for provider in self.candidates(capability)
            if provider.metadata.name not in unavailable
        )


__all__ = ["ProviderRouter"]
