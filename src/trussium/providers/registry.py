"""Ordered, explicitly composed provider registration and lookup."""

from collections.abc import Iterator, Sequence

from trussium.errors import ConfigurationError
from trussium.providers.contracts import Provider, validate_provider_name


class ProviderRegistryError(ConfigurationError):
    """Base for stable provider-registry configuration failures."""

    default_code = "provider_registry_error"


class ProviderAlreadyRegisteredError(ProviderRegistryError):
    """Raised when registration would replace an existing provider identity."""

    default_code = "provider_already_registered"

    def __init__(self, provider_name: str) -> None:
        self.provider_name = validate_provider_name(provider_name)
        super().__init__(f"Provider '{self.provider_name}' is already registered.")


class ProviderNotFoundError(ProviderRegistryError):
    """Raised when a required provider identity is not registered."""

    default_code = "provider_not_found"

    def __init__(self, provider_name: str) -> None:
        self.provider_name = validate_provider_name(provider_name)
        super().__init__(f"Provider '{self.provider_name}' is not registered.")


class ProviderRegistrySealedError(ProviderRegistryError):
    """Raised when registration is attempted after application composition."""

    default_code = "provider_registry_sealed"

    def __init__(self) -> None:
        super().__init__("Provider registry is sealed.")


class ProviderContractMismatchError(ProviderRegistryError):
    """Raised when an object does not implement the provider protocol."""

    default_code = "provider_contract_mismatch"

    def __init__(self) -> None:
        super().__init__("Registered provider does not implement the Provider contract.")


class ProviderRegistry:
    """Store explicitly composed providers in stable order until sealed."""

    def __init__(self, providers: Sequence[Provider] = ()) -> None:
        self._providers: dict[str, Provider] = {}
        self._sealed = False
        for provider in providers:
            self.register(provider)

    @property
    def names(self) -> tuple[str, ...]:
        """Return immutable provider identities in registration order."""
        return tuple(self._providers)

    @property
    def providers(self) -> tuple[Provider, ...]:
        """Return immutable provider snapshots in registration order."""
        return tuple(self._providers.values())

    @property
    def metadata(self) -> tuple[object, ...]:
        """Return immutable metadata snapshots in registration order."""
        return tuple(provider.metadata for provider in self._providers.values())

    @property
    def sealed(self) -> bool:
        """Return whether application composition has closed registration."""
        return self._sealed

    def register(self, provider: Provider) -> Provider:
        """Register one provider without replacing an existing identity."""
        if self._sealed:
            raise ProviderRegistrySealedError()
        if not isinstance(provider, Provider):
            raise ProviderContractMismatchError()
        provider_name = validate_provider_name(provider.metadata.name)
        if provider_name in self._providers:
            raise ProviderAlreadyRegisteredError(provider_name)
        self._providers[provider_name] = provider
        return provider

    def get(self, name: str) -> Provider | None:
        """Return a named provider or ``None`` when it is not registered."""
        return self._providers.get(validate_provider_name(name))

    def require(self, name: str) -> Provider:
        """Return a named provider or raise a stable configuration failure."""
        provider_name = validate_provider_name(name)
        provider = self._providers.get(provider_name)
        if provider is None:
            raise ProviderNotFoundError(provider_name)
        return provider

    def seal(self) -> tuple[Provider, ...]:
        """Close registration idempotently and return the provider snapshot."""
        self._sealed = True
        return self.providers

    def __len__(self) -> int:
        return len(self._providers)

    def __iter__(self) -> Iterator[Provider]:
        return iter(self._providers.values())

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._providers


__all__ = [
    "ProviderAlreadyRegisteredError",
    "ProviderContractMismatchError",
    "ProviderNotFoundError",
    "ProviderRegistry",
    "ProviderRegistryError",
    "ProviderRegistrySealedError",
]
