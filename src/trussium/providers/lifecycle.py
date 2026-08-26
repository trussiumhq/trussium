"""Deterministic lifecycle management for provider-owned resources."""

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from trussium.providers.contracts import Provider
from trussium.runtime import (
    RuntimeServiceLifecycle,
    RuntimeServiceLifecycleState,
)


@runtime_checkable
class ProviderService(Provider, Protocol):
    """Provider contract for adapters that own startup/shutdown resources."""

    async def startup(self) -> None:
        """Initialize provider-owned resources before serving requests."""
        ...

    async def shutdown(self) -> None:
        """Release provider-owned resources after requests drain."""
        ...


class _ProviderRuntimeService:
    """Adapt a lifecycle-aware provider to the runtime lifecycle contract."""

    def __init__(self, provider: ProviderService) -> None:
        self._provider = provider

    @property
    def name(self) -> str:
        return self._provider.metadata.name

    async def startup(self) -> None:
        await self._provider.startup()

    async def shutdown(self) -> None:
        await self._provider.shutdown()


class ProviderLifecycle:
    """Coordinate provider startup, rollback, and bounded reverse shutdown."""

    def __init__(
        self,
        providers: Sequence[ProviderService] = (),
        *,
        cleanup_timeout_seconds: float = 10.0,
    ) -> None:
        """Create a lifecycle plan without mutating provider resources."""
        resolved_providers = tuple(providers)
        if any(not isinstance(provider, ProviderService) for provider in resolved_providers):
            raise ValueError("Provider lifecycle entries must implement ProviderService")
        self._providers = resolved_providers
        self._lifecycle = RuntimeServiceLifecycle(
            tuple(_ProviderRuntimeService(provider) for provider in resolved_providers),
            cleanup_timeout_seconds=cleanup_timeout_seconds,
        )

    @property
    def providers(self) -> tuple[ProviderService, ...]:
        """Return the immutable ordered lifecycle plan."""
        return self._providers

    @property
    def state(self) -> RuntimeServiceLifecycleState:
        """Return the underlying deterministic lifecycle state."""
        return self._lifecycle.state

    @property
    def cleanup_timeout_seconds(self) -> float:
        """Return the per-provider cleanup deadline."""
        return self._lifecycle.cleanup_timeout_seconds

    async def startup(self) -> None:
        """Start providers in order and roll back partial startup."""
        await self._lifecycle.startup()

    async def shutdown(self) -> None:
        """Stop started providers in reverse order."""
        await self._lifecycle.shutdown()


__all__ = ["ProviderLifecycle", "ProviderService"]
