"""Tests for bounded provider model discovery."""

import asyncio

from fastapi.testclient import TestClient

from trussium.app import create_application
from trussium.config import RuntimeSettings, Settings
from trussium.providers import ProviderMetadata, ProviderModel, ProviderRegistry


class ModelProvider:
    def __init__(self, models: tuple[ProviderModel, ...]) -> None:
        self.metadata = ProviderMetadata(name="models", version="1.0.0")
        self.capabilities: tuple[object, ...] = ()
        self._models = models

    async def list_models(self) -> tuple[ProviderModel, ...]:
        return self._models


class MetadataOnlyProvider:
    metadata = ProviderMetadata(name="static", version="1.0.0")
    capabilities: tuple[object, ...] = ()


def test_model_discovery_returns_bounded_models_in_order() -> None:
    provider = ModelProvider((ProviderModel("model-a", "owner"), ProviderModel("model-b")))
    registry = ProviderRegistry((provider,))
    response = TestClient(create_application(provider_registry=registry)).get(
        "/v1/providers/models/models"
    )

    assert response.status_code == 200
    assert response.json() == {
        "provider": "models",
        "status": "available",
        "models": [{"id": "model-a", "owned_by": "owner"}, {"id": "model-b"}],
    }


def test_model_discovery_reports_unsupported_and_unknown_providers() -> None:
    registry = ProviderRegistry((MetadataOnlyProvider(),))
    client = TestClient(create_application(provider_registry=registry))
    unsupported = client.get("/v1/providers/static/models")
    unknown = client.get("/v1/providers/missing/models")

    assert unsupported.json()["reason"] == "model_discovery_not_supported"
    assert unsupported.json()["status"] == "unavailable"
    assert unknown.status_code == 404
    assert unknown.json()["detail"]["code"] == "provider_not_found"


def test_model_discovery_normalizes_timeout_and_duplicate_results() -> None:
    class SlowProvider(ModelProvider):
        async def list_models(self) -> tuple[ProviderModel, ...]:
            await asyncio.sleep(0.02)
            return self._models

    timeout_client = TestClient(
        create_application(
            settings=Settings(runtime=RuntimeSettings(model_discovery_timeout_seconds=0.001)),
            provider_registry=ProviderRegistry((SlowProvider(()),)),
        )
    )
    timeout = timeout_client.get("/v1/providers/models/models")
    assert timeout.json()["reason"] == "model_discovery_timeout"

    duplicate = ModelProvider((ProviderModel("same"), ProviderModel("same")))
    duplicate_client = TestClient(
        create_application(provider_registry=ProviderRegistry((duplicate,)))
    )
    result = duplicate_client.get("/v1/providers/models/models")
    assert result.json()["reason"] == "model_discovery_failed"
