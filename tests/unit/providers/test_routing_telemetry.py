import asyncio

from trussium.providers import ProviderMetadata, ProviderRegistry, ProviderRouter, RoutingDecision


class ProviderStub:
    def __init__(self, name: str) -> None:
        self.metadata = ProviderMetadata(
            name=name,
            version="1.0.0",
            capabilities=("chat.completions",),
        )
        self.capabilities: tuple[object, ...] = ()


def test_routing_decisions_are_emitted_for_fallback_and_success() -> None:
    registry = ProviderRegistry((ProviderStub("first"), ProviderStub("second")))
    registry.seal()
    decisions: list[RoutingDecision] = []
    attempts = 0

    async def operation(_: object) -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ConnectionError("temporary")
        return "ok"

    result = asyncio.run(
        ProviderRouter(registry).execute_with_fallback(
            "chat.completions", operation, decision_handler=decisions.append
        )
    )
    assert result == "ok"
    assert [(item.provider, item.outcome) for item in decisions] == [
        ("first", "fallback"),
        ("second", "success"),
    ]
