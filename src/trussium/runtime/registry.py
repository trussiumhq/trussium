"""Ordered registration and lookup for application-scoped runtime services."""

from collections.abc import Iterator, Sequence

from trussium.errors import ConfigurationError
from trussium.runtime.lifecycle import RuntimeService, validate_runtime_service_name


class RuntimeServiceRegistryError(ConfigurationError):
    """Base for stable runtime-service registry configuration failures."""

    default_code = "runtime_service_registry_error"


class RuntimeServiceAlreadyRegisteredError(RuntimeServiceRegistryError):
    """Raised when registration would replace an existing service identity."""

    default_code = "runtime_service_already_registered"

    def __init__(self, service_name: str) -> None:
        """Initialize a bounded duplicate-registration failure."""
        self.service_name = validate_runtime_service_name(service_name)
        super().__init__(f"Runtime service '{self.service_name}' is already registered.")


class RuntimeServiceNotFoundError(RuntimeServiceRegistryError):
    """Raised when a required service identity is not registered."""

    default_code = "runtime_service_not_found"

    def __init__(self, service_name: str) -> None:
        """Initialize a bounded required-lookup failure."""
        self.service_name = validate_runtime_service_name(service_name)
        super().__init__(f"Runtime service '{self.service_name}' is not registered.")


class RuntimeServiceRegistrySealedError(RuntimeServiceRegistryError):
    """Raised when registration is attempted after application composition."""

    default_code = "runtime_service_registry_sealed"

    def __init__(self) -> None:
        """Initialize a bounded sealed-registry failure."""
        super().__init__("Runtime service registry is sealed.")


class RuntimeServiceRegistry:
    """Store runtime services in stable registration order until sealed."""

    def __init__(self, services: Sequence[RuntimeService] = ()) -> None:
        """Create a registry and explicitly register its initial services."""
        self._services: dict[str, RuntimeService] = {}
        self._sealed = False

        for service in services:
            self.register(service)

    @property
    def names(self) -> tuple[str, ...]:
        """Return an immutable ordered snapshot of registered names."""
        return tuple(self._services)

    @property
    def services(self) -> tuple[RuntimeService, ...]:
        """Return an immutable ordered snapshot of registered services."""
        return tuple(self._services.values())

    @property
    def sealed(self) -> bool:
        """Return whether application composition has closed registration."""
        return self._sealed

    def register(self, service: RuntimeService) -> RuntimeService:
        """Register one service without replacing an existing identity."""
        if self._sealed:
            raise RuntimeServiceRegistrySealedError()

        service_name = validate_runtime_service_name(service.name)
        if service_name in self._services:
            raise RuntimeServiceAlreadyRegisteredError(service_name)

        self._services[service_name] = service
        return service

    def get(self, name: str) -> RuntimeService | None:
        """Return the named service, or ``None`` when it is not registered."""
        return self._services.get(validate_runtime_service_name(name))

    def require(self, name: str) -> RuntimeService:
        """Return the named service or raise a stable configuration failure."""
        service_name = validate_runtime_service_name(name)
        service = self._services.get(service_name)
        if service is None:
            raise RuntimeServiceNotFoundError(service_name)

        return service

    def seal(self) -> tuple[RuntimeService, ...]:
        """Close registration idempotently and return the lifecycle snapshot."""
        self._sealed = True
        return self.services

    def __len__(self) -> int:
        """Return the current number of registered services."""
        return len(self._services)

    def __iter__(self) -> Iterator[RuntimeService]:
        """Iterate over services in stable registration order."""
        return iter(self._services.values())

    def __contains__(self, name: object) -> bool:
        """Return whether a string identity is registered."""
        return isinstance(name, str) and name in self._services


__all__ = [
    "RuntimeServiceAlreadyRegisteredError",
    "RuntimeServiceNotFoundError",
    "RuntimeServiceRegistry",
    "RuntimeServiceRegistryError",
    "RuntimeServiceRegistrySealedError",
]
