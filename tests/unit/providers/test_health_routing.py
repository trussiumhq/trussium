import asyncio

from trussium.providers import (
    Provider,
    ProviderHealth,
    ProviderHealthReport,
    ProviderHealthStatus,
    ProviderMetadata,
    ProviderRegistry,
    ProviderRouter,
)


class ProviderStub:
    def __init__(self, name: str) -> None:
        self.metadata = ProviderMetadata(
            name=name,
            version="1.0.0",
            capabilities=("chat.completions",),
        )
        self.capabilities: tuple[object, ...] = ()

    async def check_health(self) -> ProviderHealth:
        return ProviderHealth(self.metadata.name, ProviderHealthStatus.OK)


class HealthStub:
    async def report(self) -> ProviderHealthReport:
        return ProviderHealthReport(
            ProviderHealthStatus.UNAVAILABLE,
            (
                ProviderHealth("down", ProviderHealthStatus.UNAVAILABLE),
                ProviderHealth("up", ProviderHealthStatus.OK),
            ),
        )


def test_health_aware_fallback_excludes_unavailable_provider() -> None:
    registry = ProviderRegistry((ProviderStub("down"), ProviderStub("up")))
    registry.seal()
    router = ProviderRouter(registry, health_reporter=HealthStub())  # type: ignore[arg-type]
    attempts: list[str] = []

    async def operation(provider: Provider) -> str:
        attempts.append(provider.metadata.name)
        return "ok"

    assert asyncio.run(router.execute_with_fallback("chat.completions", operation)) == "ok"
    assert attempts == ["up"]
