"""Tests for deterministic provider-priority routing."""

import asyncio

import pytest

from trussium.providers import ProviderMetadata, ProviderRegistry, ProviderRouter


class StubProvider:
    def __init__(self, name: str, capabilities: tuple[str, ...]) -> None:
        self.metadata = ProviderMetadata(name=name, version="1.0.0", capabilities=capabilities)
        self.capabilities: tuple[object, ...] = ()


def test_router_selects_first_priority_provider_advertising_capability() -> None:
    registry = ProviderRegistry(
        (
            StubProvider("first", ("chat.completions",)),
            StubProvider("second", ("chat.completions",)),
        )
    )
    registry.seal()

    router = ProviderRouter(registry, priority=("second", "first"))

    assert router.select("chat.completions") is registry.get("second")
    assert router.priority == ("second", "first")


def test_router_falls_back_to_registry_order_without_priority() -> None:
    first = StubProvider("first", ("chat.completions",))
    second = StubProvider("second", ("chat.completions",))
    registry = ProviderRegistry((first, second))
    registry.seal()

    assert ProviderRouter(registry).select("chat.completions") is first
    assert ProviderRouter(registry).select("embeddings") is None


def test_router_requires_sealed_registry_and_unique_priority() -> None:
    registry = ProviderRegistry((StubProvider("first", ()),))
    with pytest.raises(ValueError, match="sealed"):
        ProviderRouter(registry)

    registry.seal()
    with pytest.raises(ValueError, match="unique"):
        ProviderRouter(registry, priority=("first", "first"))


def test_fallback_uses_priority_order_for_transient_failures() -> None:
    first = StubProvider("first", ("chat.completions",))
    second = StubProvider("second", ("chat.completions",))
    registry = ProviderRegistry((first, second))
    registry.seal()
    router = ProviderRouter(registry, priority=("second", "first"))
    attempts: list[str] = []

    async def operation(provider: object) -> str:
        attempts.append(provider.metadata.name)  # type: ignore[union-attr]
        if len(attempts) == 1:
            raise ConnectionError("temporary")
        return "ok"

    assert asyncio.run(router.execute_with_fallback("chat.completions", operation)) == "ok"
    assert attempts == ["second", "first"]
