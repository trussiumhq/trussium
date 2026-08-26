"""Tests for explicit ordered provider registration."""

import pytest

from trussium.errors import ConfigurationError, TrussiumError
from trussium.providers import (
    Provider,
    ProviderAlreadyRegisteredError,
    ProviderContractMismatchError,
    ProviderMetadata,
    ProviderNotFoundError,
    ProviderRegistry,
    ProviderRegistryError,
    ProviderRegistrySealedError,
)


class StubProvider:
    def __init__(self, name: str) -> None:
        self.metadata = ProviderMetadata(name=name, version="1.0.0")
        self.capabilities: tuple[object, ...] = ()


def test_registration_and_discovery_preserve_order() -> None:
    first, second = StubProvider("first"), StubProvider("second")
    registry = ProviderRegistry((first,))

    assert registry.register(second) is second
    assert registry.names == ("first", "second")
    assert registry.providers == (first, second)
    assert registry.metadata == (first.metadata, second.metadata)
    assert tuple(registry) == (first, second)
    assert len(registry) == 2
    assert "first" in registry
    assert object() not in registry
    assert registry.get("second") is second
    assert registry.get("missing") is None
    assert registry.require("first") is first


def test_duplicate_registration_is_typed_and_preserves_original() -> None:
    original = StubProvider("openai")
    registry = ProviderRegistry((original,))
    with pytest.raises(ProviderAlreadyRegisteredError) as captured:
        registry.register(StubProvider("openai"))

    error = captured.value
    assert isinstance(error, ProviderRegistryError)
    assert isinstance(error, ConfigurationError)
    assert isinstance(error, TrussiumError)
    assert error.provider_name == "openai"
    assert error.code == "provider_already_registered"
    assert registry.providers == (original,)


def test_registry_rejects_non_provider_objects() -> None:
    with pytest.raises(ProviderContractMismatchError):
        ProviderRegistry().register(object())  # type: ignore[arg-type]


def test_missing_provider_has_stable_typed_failure() -> None:
    with pytest.raises(ProviderNotFoundError) as captured:
        ProviderRegistry().require("openai")
    error = captured.value
    assert error.code == "provider_not_found"
    assert error.message == "Provider 'openai' is not registered."


def test_seal_is_idempotent_and_prevents_registration() -> None:
    provider = StubProvider("openai")
    registry = ProviderRegistry((provider,))
    assert registry.seal() == registry.seal() == (provider,)
    assert registry.sealed is True
    with pytest.raises(ProviderRegistrySealedError):
        registry.register(StubProvider("later"))


@pytest.mark.parametrize("name", ["", "OpenAI", "has space", "a" * 65])
def test_lookup_reuses_provider_name_validation(name: str) -> None:
    registry = ProviderRegistry()
    with pytest.raises(ValueError, match="must match"):
        registry.get(name)
    with pytest.raises(ValueError, match="must match"):
        registry.require(name)


def test_protocol_is_exported_and_runtime_checkable() -> None:
    assert isinstance(StubProvider("fake"), Provider)
