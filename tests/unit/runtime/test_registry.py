"""Tests for ordered runtime-service registration and lookup."""

import pytest

from trussium.errors import ConfigurationError, TrussiumError
from trussium.runtime import (
    RuntimeServiceAlreadyRegisteredError,
    RuntimeServiceNotFoundError,
    RuntimeServiceRegistry,
    RuntimeServiceRegistryError,
    RuntimeServiceRegistrySealedError,
)


class StubRuntimeService:
    """Minimal service implementation used by registry tests."""

    def __init__(self, name: str) -> None:
        """Store the stable service name."""
        self.name = name

    async def startup(self) -> None:
        """Implement the service startup contract."""

    async def shutdown(self) -> None:
        """Implement the service shutdown contract."""


def test_registration_and_discovery_preserve_insertion_order() -> None:
    """All discovery surfaces should follow explicit registration order."""
    first = StubRuntimeService("first")
    second = StubRuntimeService("second")
    registry = RuntimeServiceRegistry((first,))

    registered = registry.register(second)

    assert registered is second
    assert registry.names == ("first", "second")
    assert registry.services == (first, second)
    assert tuple(registry) == (first, second)
    assert len(registry) == 2
    assert "first" in registry
    assert "missing" not in registry
    assert object() not in registry
    assert registry.get("first") is first
    assert registry.get("missing") is None
    assert registry.require("second") is second


def test_discovery_snapshots_do_not_expose_later_mutation() -> None:
    """Previously returned tuple snapshots must remain immutable and stable."""
    first = StubRuntimeService("first")
    second = StubRuntimeService("second")
    registry = RuntimeServiceRegistry((first,))
    names_snapshot = registry.names
    services_snapshot = registry.services

    registry.register(second)

    assert names_snapshot == ("first",)
    assert services_snapshot == (first,)
    assert registry.names == ("first", "second")
    assert registry.services == (first, second)


def test_duplicate_registration_is_typed_and_preserves_original() -> None:
    """A duplicate identity must never replace or reorder its first service."""
    original = StubRuntimeService("cache")
    duplicate = StubRuntimeService("cache")
    registry = RuntimeServiceRegistry((original,))

    with pytest.raises(RuntimeServiceAlreadyRegisteredError) as captured:
        registry.register(duplicate)

    error = captured.value
    assert isinstance(error, RuntimeServiceRegistryError)
    assert isinstance(error, ConfigurationError)
    assert isinstance(error, TrussiumError)
    assert isinstance(error, RuntimeError)
    assert error.service_name == "cache"
    assert error.code == "runtime_service_already_registered"
    assert error.message == "Runtime service 'cache' is already registered."
    assert registry.services == (original,)


def test_constructor_rejects_duplicate_registration() -> None:
    """Constructor registration should enforce the same duplicate contract."""
    with pytest.raises(RuntimeServiceAlreadyRegisteredError):
        RuntimeServiceRegistry((StubRuntimeService("cache"), StubRuntimeService("cache")))


def test_required_lookup_has_stable_typed_failure() -> None:
    """Missing required services should expose bounded configuration metadata."""
    registry = RuntimeServiceRegistry()

    with pytest.raises(RuntimeServiceNotFoundError) as captured:
        registry.require("cache")

    error = captured.value
    assert isinstance(error, RuntimeServiceRegistryError)
    assert isinstance(error, ConfigurationError)
    assert error.service_name == "cache"
    assert error.code == "runtime_service_not_found"
    assert error.message == "Runtime service 'cache' is not registered."


@pytest.mark.parametrize("name", ["", "UPPER", "has space", "a" * 65])
def test_registration_and_lookup_reuse_service_name_validation(name: str) -> None:
    """Registration and named lookup should share the lifecycle name boundary."""
    registry = RuntimeServiceRegistry()

    with pytest.raises(ValueError, match="must match"):
        registry.register(StubRuntimeService(name))
    with pytest.raises(ValueError, match="must match"):
        registry.get(name)
    with pytest.raises(ValueError, match="must match"):
        registry.require(name)


def test_seal_is_idempotent_and_prevents_further_registration() -> None:
    """Composition should close mutation without changing discovery behavior."""
    service = StubRuntimeService("cache")
    registry = RuntimeServiceRegistry((service,))

    first_snapshot = registry.seal()
    second_snapshot = registry.seal()

    assert registry.sealed is True
    assert first_snapshot == second_snapshot == (service,)
    assert registry.get("cache") is service

    with pytest.raises(RuntimeServiceRegistrySealedError) as captured:
        registry.register(StubRuntimeService("later"))

    error = captured.value
    assert isinstance(error, RuntimeServiceRegistryError)
    assert isinstance(error, ConfigurationError)
    assert error.code == "runtime_service_registry_sealed"
    assert error.message == "Runtime service registry is sealed."
    assert registry.services == (service,)
