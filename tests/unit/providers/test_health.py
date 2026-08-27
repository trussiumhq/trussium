"""Tests for provider health reporting."""

import asyncio

from trussium.providers import (
    ProviderHealth,
    ProviderHealthReporter,
    ProviderHealthStatus,
    ProviderMetadata,
    ProviderRegistry,
)


class HealthyProvider:
    metadata = ProviderMetadata(name="healthy", version="1.0.0")
    capabilities: tuple[object, ...] = ()

    async def check_health(self) -> ProviderHealth:
        return ProviderHealth("healthy", ProviderHealthStatus.OK)


class UnknownProvider:
    metadata = ProviderMetadata(name="unknown", version="1.0.0")
    capabilities: tuple[object, ...] = ()


def test_provider_health_report_is_ordered_and_informational() -> None:
    registry = ProviderRegistry((HealthyProvider(), UnknownProvider()))
    registry.seal()
    report = asyncio.run(ProviderHealthReporter(registry).report())
    assert report.status is ProviderHealthStatus.UNKNOWN
    assert report.providers == (
        ProviderHealth("healthy", ProviderHealthStatus.OK),
        ProviderHealth("unknown", ProviderHealthStatus.UNKNOWN, "health_not_reported"),
    )
