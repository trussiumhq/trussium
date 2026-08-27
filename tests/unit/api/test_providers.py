"""Tests for bounded provider discovery."""

from fastapi.testclient import TestClient

from trussium.app import create_application
from trussium.providers import ProviderMetadata, ProviderRegistry


class StubProvider:
    def __init__(self, name: str, capabilities: tuple[str, ...]) -> None:
        self.metadata = ProviderMetadata(
            name=name,
            version="1.2.3",
            capabilities=capabilities,
            description="A test provider",
        )
        self.capabilities: tuple[object, ...] = ()


def test_empty_provider_discovery_is_stable() -> None:
    response = TestClient(create_application()).get("/v1/providers")
    assert response.status_code == 200
    assert response.json() == {"providers": []}


def test_provider_health_is_informational_and_ordered() -> None:
    registry = ProviderRegistry((StubProvider("first", ()), StubProvider("second", ())))
    response = TestClient(create_application(provider_registry=registry)).get(
        "/v1/providers/health"
    )
    assert response.status_code == 200
    assert response.json() == {
        "status": "unknown",
        "providers": [
            {"name": "first", "status": "unknown", "reason": "health_not_reported"},
            {"name": "second", "status": "unknown", "reason": "health_not_reported"},
        ],
    }


def test_provider_discovery_preserves_registry_order_and_privacy() -> None:
    registry = ProviderRegistry(
        (
            StubProvider("first", ("chat.completions",)),
            StubProvider("second", ("audio.speech", "translation")),
        )
    )
    response = TestClient(create_application(provider_registry=registry)).get("/v1/providers")

    assert response.status_code == 200
    assert response.json() == {
        "providers": [
            {
                "name": "first",
                "version": "1.2.3",
                "capabilities": ["chat.completions"],
                "description": "A test provider",
            },
            {
                "name": "second",
                "version": "1.2.3",
                "capabilities": ["audio.speech", "translation"],
                "description": "A test provider",
            },
        ]
    }
    body = response.text
    for forbidden in ("endpoint", "api_key", "secret", "model", "implementation", "health"):
        assert forbidden not in body


def test_provider_discovery_does_not_mutate_registry() -> None:
    registry = ProviderRegistry((StubProvider("first", ("chat.completions",)),))
    app = create_application(provider_registry=registry)
    TestClient(app).get("/v1/providers")
    assert registry.sealed is True
    assert registry.names == ("first",)
