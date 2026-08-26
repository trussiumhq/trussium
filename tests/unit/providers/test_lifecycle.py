"""Tests for deterministic provider resource lifecycle management."""

import asyncio

import pytest

from trussium.providers import ProviderLifecycle, ProviderMetadata, ProviderService
from trussium.runtime import RuntimeServiceLifecycleError


class StubProvider:
    def __init__(self, name: str, events: list[str], *, fail_start: bool = False) -> None:
        self.metadata = ProviderMetadata(name=name, version="1.0.0")
        self.capabilities: tuple[object, ...] = ()
        self._events = events
        self._fail_start = fail_start

    async def startup(self) -> None:
        self._events.append(f"start:{self.metadata.name}")
        if self._fail_start:
            raise RuntimeError("startup failed")

    async def shutdown(self) -> None:
        self._events.append(f"stop:{self.metadata.name}")


def test_provider_lifecycle_starts_in_order_and_stops_in_reverse() -> None:
    events: list[str] = []
    first, second = StubProvider("first", events), StubProvider("second", events)
    lifecycle = ProviderLifecycle((first, second))

    async def exercise() -> None:
        await lifecycle.startup()
        await lifecycle.shutdown()

    asyncio.run(exercise())
    assert events == ["start:first", "start:second", "stop:second", "stop:first"]
    assert isinstance(first, ProviderService)


def test_provider_lifecycle_rolls_back_partial_startup() -> None:
    events: list[str] = []
    lifecycle = ProviderLifecycle(
        (StubProvider("first", events), StubProvider("second", events, fail_start=True))
    )

    with pytest.raises(RuntimeServiceLifecycleError):
        asyncio.run(lifecycle.startup())

    assert events == ["start:first", "start:second", "stop:first"]


def test_provider_lifecycle_rejects_non_lifecycle_provider() -> None:
    class MetadataOnly:
        metadata = ProviderMetadata(name="metadata-only", version="1.0.0")
        capabilities: tuple[object, ...] = ()

    with pytest.raises(ValueError, match="ProviderService"):
        ProviderLifecycle((MetadataOnly(),))  # type: ignore[arg-type]
