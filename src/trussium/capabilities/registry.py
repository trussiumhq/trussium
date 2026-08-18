"""Ordered provider-neutral capability registration and lookup."""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import TypeVar

from trussium.capabilities.metadata import CapabilityMetadata, validate_capability_name
from trussium.errors import ConfigurationError

CapabilityT = TypeVar("CapabilityT")


@dataclass(frozen=True, slots=True, init=False)
class CapabilityRegistration:
    """Immutable association between one capability identity and implementation."""

    name: str
    capability: object
    metadata: CapabilityMetadata

    def __init__(
        self,
        name: str,
        capability: object,
        metadata: CapabilityMetadata | None = None,
    ) -> None:
        """Validate identity and bind explicit or legacy-compatible metadata."""
        capability_name = validate_capability_name(name)
        if capability is None:
            raise ValueError("Registered capability must not be None")
        resolved_metadata = metadata or CapabilityMetadata(name=capability_name)
        if not isinstance(resolved_metadata, CapabilityMetadata):
            raise ValueError("Registered capability metadata must be CapabilityMetadata")
        if resolved_metadata.name != capability_name:
            raise ValueError("Capability metadata name must match its registration name")

        object.__setattr__(self, "name", capability_name)
        object.__setattr__(self, "capability", capability)
        object.__setattr__(self, "metadata", resolved_metadata)


class CapabilityRegistryError(ConfigurationError):
    """Base for stable capability-registry configuration failures."""

    default_code = "capability_registry_error"


class CapabilityAlreadyRegisteredError(CapabilityRegistryError):
    """Raised when registration would replace an existing capability identity."""

    default_code = "capability_already_registered"

    def __init__(self, capability_name: str) -> None:
        """Initialize a bounded duplicate-registration failure."""
        self.capability_name = validate_capability_name(capability_name)
        super().__init__(f"Capability '{self.capability_name}' is already registered.")


class CapabilityNotFoundError(CapabilityRegistryError):
    """Raised when a required capability identity is not registered."""

    default_code = "capability_not_found"

    def __init__(self, capability_name: str) -> None:
        """Initialize a bounded required-lookup failure."""
        self.capability_name = validate_capability_name(capability_name)
        super().__init__(f"Capability '{self.capability_name}' is not registered.")


class CapabilityRegistrySealedError(CapabilityRegistryError):
    """Raised when registration is attempted after application composition."""

    default_code = "capability_registry_sealed"

    def __init__(self) -> None:
        """Initialize a bounded sealed-registry failure."""
        super().__init__("Capability registry is sealed.")


class CapabilityContractMismatchError(CapabilityRegistryError):
    """Raised when a known identity does not implement its required protocol."""

    default_code = "capability_contract_mismatch"

    def __init__(self, capability_name: str) -> None:
        """Initialize a bounded protocol-mismatch failure."""
        self.capability_name = validate_capability_name(capability_name)
        super().__init__(
            f"Capability '{self.capability_name}' does not implement its required contract."
        )


class CapabilityRegistry:
    """Store provider-neutral capabilities in stable registration order until sealed."""

    def __init__(self, registrations: Sequence[CapabilityRegistration] = ()) -> None:
        """Create a registry and explicitly add its initial registrations."""
        self._registrations: dict[str, CapabilityRegistration] = {}
        self._sealed = False

        for registration in registrations:
            self.register(
                registration.name,
                registration.capability,
                metadata=registration.metadata,
            )

    @property
    def names(self) -> tuple[str, ...]:
        """Return an immutable ordered snapshot of registered names."""
        return tuple(self._registrations)

    @property
    def capabilities(self) -> tuple[object, ...]:
        """Return an immutable ordered snapshot of capability implementations."""
        return tuple(registration.capability for registration in self._registrations.values())

    @property
    def registrations(self) -> tuple[CapabilityRegistration, ...]:
        """Return immutable ordered identity and implementation snapshots."""
        return tuple(self._registrations.values())

    @property
    def metadata(self) -> tuple[CapabilityMetadata, ...]:
        """Return an immutable ordered public metadata snapshot."""
        return tuple(registration.metadata for registration in self._registrations.values())

    @property
    def sealed(self) -> bool:
        """Return whether application composition has closed registration."""
        return self._sealed

    def register(
        self,
        name: str,
        capability: CapabilityT,
        *,
        metadata: CapabilityMetadata | None = None,
    ) -> CapabilityT:
        """Register one implementation without replacing an existing identity."""
        if self._sealed:
            raise CapabilityRegistrySealedError()

        registration = CapabilityRegistration(
            name=name,
            capability=capability,
            metadata=metadata,
        )
        if registration.name in self._registrations:
            raise CapabilityAlreadyRegisteredError(registration.name)

        self._registrations[registration.name] = registration
        return capability

    def get(self, name: str) -> object | None:
        """Return the named implementation, or ``None`` when it is absent."""
        registration = self._registrations.get(validate_capability_name(name))
        return None if registration is None else registration.capability

    def require(self, name: str) -> object:
        """Return the named implementation or raise a stable configuration failure."""
        capability_name = validate_capability_name(name)
        registration = self._registrations.get(capability_name)
        if registration is None:
            raise CapabilityNotFoundError(capability_name)

        return registration.capability

    def get_metadata(self, name: str) -> CapabilityMetadata | None:
        """Return public metadata for the named capability, or ``None`` when absent."""
        registration = self._registrations.get(validate_capability_name(name))
        return None if registration is None else registration.metadata

    def require_metadata(self, name: str) -> CapabilityMetadata:
        """Return named public metadata or raise a stable configuration failure."""
        capability_name = validate_capability_name(name)
        registration = self._registrations.get(capability_name)
        if registration is None:
            raise CapabilityNotFoundError(capability_name)

        return registration.metadata

    def seal(self) -> tuple[CapabilityRegistration, ...]:
        """Close registration idempotently and return the ordered composition snapshot."""
        self._sealed = True
        return self.registrations

    def __len__(self) -> int:
        """Return the current number of registered capabilities."""
        return len(self._registrations)

    def __iter__(self) -> Iterator[CapabilityRegistration]:
        """Iterate over registrations in stable insertion order."""
        return iter(self._registrations.values())

    def __contains__(self, name: object) -> bool:
        """Return whether a string identity is registered."""
        return isinstance(name, str) and name in self._registrations


__all__ = [
    "CapabilityAlreadyRegisteredError",
    "CapabilityContractMismatchError",
    "CapabilityMetadata",
    "CapabilityNotFoundError",
    "CapabilityRegistration",
    "CapabilityRegistry",
    "CapabilityRegistryError",
    "CapabilityRegistrySealedError",
    "validate_capability_name",
]
