"""Tests for explicit provider plugin loading."""

import pytest

from trussium.providers import (
    ProviderAlreadyRegisteredError,
    ProviderMetadata,
    ProviderPluginCompatibilityError,
    ProviderPluginLoader,
    ProviderPluginLoadError,
    ProviderPluginNotFoundError,
    ProviderPluginPermissionError,
    ProviderPluginSpec,
    ProviderRegistry,
    ProviderRegistrySealedError,
)


class StubProvider:
    def __init__(self, name: str = "example") -> None:
        self.metadata = ProviderMetadata(name=name, version="1.0.0")
        self.capabilities: tuple[object, ...] = ()


def test_loader_loads_allowlisted_plugin_into_registry() -> None:
    loader = ProviderPluginLoader((ProviderPluginSpec("example", "v1", StubProvider),))
    registry = ProviderRegistry()

    loaded = loader.load_into(registry)

    assert loader.names == ("example",)
    assert loaded[0].metadata.name == "example"
    assert registry.names == ("example",)


def test_loader_rejects_unknown_plugin_and_incompatible_version() -> None:
    loader = ProviderPluginLoader((ProviderPluginSpec("example", "v2", StubProvider),))
    with pytest.raises(ProviderPluginNotFoundError):
        loader.load("missing")
    with pytest.raises(ProviderPluginCompatibilityError):
        loader.load("example")


def test_loader_enforces_explicit_permissions() -> None:
    spec = ProviderPluginSpec("example", "v1", StubProvider, frozenset({"network"}))
    with pytest.raises(ProviderPluginPermissionError):
        ProviderPluginLoader((spec,)).load("example")

    loader = ProviderPluginLoader((spec,), allowed_permissions=frozenset({"network"}))
    assert loader.load("example").metadata.name == "example"


def test_loader_rejects_invalid_factory_result() -> None:
    def invalid_factory() -> object:
        return object()

    loader = ProviderPluginLoader(
        (ProviderPluginSpec("example", "v1", invalid_factory),)  # type: ignore[arg-type]
    )
    with pytest.raises(ProviderPluginLoadError):
        loader.load("example")


def test_loader_rejects_duplicate_specs_and_sealed_registry() -> None:
    with pytest.raises(ValueError, match="duplicated"):
        ProviderPluginLoader(
            (
                ProviderPluginSpec("example", "v1", StubProvider),
                ProviderPluginSpec("example", "v1", StubProvider),
            )
        )
    registry = ProviderRegistry()
    registry.seal()
    loader = ProviderPluginLoader((ProviderPluginSpec("example", "v1", StubProvider),))
    with pytest.raises(ProviderRegistrySealedError):
        loader.load_into(registry)


def test_loader_preflights_duplicate_names_before_registry_mutation() -> None:
    registry = ProviderRegistry()
    loader = ProviderPluginLoader(
        (
            ProviderPluginSpec("first", "v1", lambda: StubProvider("first")),
            ProviderPluginSpec("second", "v1", lambda: StubProvider("second")),
        )
    )

    with pytest.raises(ProviderAlreadyRegisteredError):
        loader.load_into(registry, ("first", "first"))
    assert registry.names == ()
