"""Explicit, allowlisted provider plugin loading contracts."""

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import Final

from trussium.errors import ConfigurationError
from trussium.providers.contracts import Provider, validate_provider_name
from trussium.providers.registry import (
    ProviderAlreadyRegisteredError,
    ProviderRegistry,
    ProviderRegistrySealedError,
)

PLUGIN_API_VERSION: Final = "v1"
PLUGIN_PERMISSIONS: Final = frozenset({"network", "filesystem", "subprocess", "credentials"})


class ProviderPluginError(ConfigurationError):
    """Base for bounded provider plugin configuration failures."""

    default_code = "provider_plugin_error"


class ProviderPluginNotFoundError(ProviderPluginError):
    """Raised when an explicitly requested plugin is not allowlisted."""

    default_code = "provider_plugin_not_found"

    def __init__(self, plugin_name: str) -> None:
        self.plugin_name = validate_provider_name(plugin_name)
        super().__init__(f"Provider plugin '{self.plugin_name}' is not allowlisted.")


class ProviderPluginCompatibilityError(ProviderPluginError):
    """Raised when a plugin targets an unsupported Trussium API version."""

    default_code = "provider_plugin_incompatible"

    def __init__(self, plugin_name: str, api_version: str) -> None:
        self.plugin_name = validate_provider_name(plugin_name)
        self.api_version = api_version
        super().__init__(
            f"Provider plugin '{self.plugin_name}' targets an unsupported API version."
        )


class ProviderPluginPermissionError(ProviderPluginError):
    """Raised when a plugin requests permissions outside the application policy."""

    default_code = "provider_plugin_permission_denied"

    def __init__(self, plugin_name: str, permission: str) -> None:
        self.plugin_name = validate_provider_name(plugin_name)
        self.permission = permission
        super().__init__(f"Provider plugin '{self.plugin_name}' requests an unapproved permission.")


class ProviderPluginLoadError(ProviderPluginError):
    """Raised when a trusted plugin factory cannot produce a valid provider."""

    default_code = "provider_plugin_load_failed"

    def __init__(self, plugin_name: str) -> None:
        self.plugin_name = validate_provider_name(plugin_name)
        super().__init__(f"Provider plugin '{self.plugin_name}' could not be loaded.")


@dataclass(frozen=True, slots=True)
class ProviderPluginSpec:
    """Immutable allowlisted description of one trusted plugin factory."""

    name: str
    api_version: str
    factory: Callable[[], Provider]
    permissions: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        validate_provider_name(self.name)
        if not callable(self.factory):
            raise ValueError("Provider plugin factory must be callable")
        if self.permissions - PLUGIN_PERMISSIONS:
            raise ValueError("Provider plugin permissions contain an unsupported value")


class ProviderPluginLoader:
    """Load only explicitly supplied, allowlisted provider plugin specs."""

    def __init__(
        self,
        specs: Sequence[ProviderPluginSpec] = (),
        *,
        api_version: str = PLUGIN_API_VERSION,
        allowed_permissions: frozenset[str] = frozenset(),
    ) -> None:
        """Create a deterministic loader policy without importing packages."""
        if allowed_permissions - PLUGIN_PERMISSIONS:
            raise ValueError("Allowed plugin permissions contain an unsupported value")
        self._api_version = api_version
        self._allowed_permissions = allowed_permissions
        self._specs: dict[str, ProviderPluginSpec] = {}
        for spec in specs:
            if spec.name in self._specs:
                raise ValueError(f"Provider plugin '{spec.name}' is duplicated")
            self._specs[spec.name] = spec

    @property
    def names(self) -> tuple[str, ...]:
        """Return allowlisted plugin names in declaration order."""
        return tuple(self._specs)

    @property
    def specs(self) -> tuple[ProviderPluginSpec, ...]:
        """Return immutable allowlisted plugin specifications."""
        return tuple(self._specs.values())

    def load(self, name: str) -> Provider:
        """Validate and construct one explicitly requested provider plugin."""
        plugin_name = validate_provider_name(name)
        spec = self._specs.get(plugin_name)
        if spec is None:
            raise ProviderPluginNotFoundError(plugin_name)
        if spec.api_version != self._api_version:
            raise ProviderPluginCompatibilityError(plugin_name, spec.api_version)
        for permission in sorted(spec.permissions):
            if permission not in self._allowed_permissions:
                raise ProviderPluginPermissionError(plugin_name, permission)
        try:
            provider = spec.factory()
        except Exception as error:
            raise ProviderPluginLoadError(plugin_name) from error
        if not isinstance(provider, Provider) or provider.metadata.name != plugin_name:
            raise ProviderPluginLoadError(plugin_name)
        return provider

    def load_into(
        self, registry: ProviderRegistry, names: Sequence[str] | None = None
    ) -> tuple[Provider, ...]:
        """Load requested plugins and register them in declaration order."""
        requested = self.names if names is None else tuple(names)
        if registry.sealed:
            raise ProviderRegistrySealedError()
        requested_names = tuple(validate_provider_name(name) for name in requested)
        if len(set(requested_names)) != len(requested_names):
            duplicate = next(
                name
                for index, name in enumerate(requested_names)
                if name in requested_names[:index]
            )
            raise ProviderAlreadyRegisteredError(duplicate)
        for name in requested_names:
            if name in registry:
                raise ProviderAlreadyRegisteredError(name)
        loaded = tuple(self.load(name) for name in requested_names)
        for provider in loaded:
            registry.register(provider)
        return loaded

    def __len__(self) -> int:
        return len(self._specs)

    def __iter__(self) -> Iterator[ProviderPluginSpec]:
        return iter(self._specs.values())


__all__ = [
    "PLUGIN_API_VERSION",
    "PLUGIN_PERMISSIONS",
    "ProviderPluginCompatibilityError",
    "ProviderPluginError",
    "ProviderPluginLoadError",
    "ProviderPluginLoader",
    "ProviderPluginNotFoundError",
    "ProviderPluginPermissionError",
    "ProviderPluginSpec",
]
