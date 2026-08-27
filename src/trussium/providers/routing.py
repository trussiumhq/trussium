"""Deterministic provider-priority selection."""

from collections.abc import Sequence

from trussium.providers.contracts import Provider, validate_provider_name
from trussium.providers.registry import ProviderRegistry


class ProviderRouter:
    """Select the first registered provider matching a capability."""

    def __init__(self, registry: ProviderRegistry, priority: Sequence[str] = ()) -> None:
        if not registry.sealed:
            raise ValueError("Provider routing requires a sealed registry")
        normalized = tuple(validate_provider_name(name) for name in priority)
        if len(normalized) != len(set(normalized)):
            raise ValueError("Provider routing priorities must be unique")
        self._registry = registry
        self._priority = normalized

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


__all__ = ["ProviderRouter"]
