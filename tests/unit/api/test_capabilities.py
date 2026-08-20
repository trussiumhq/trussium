"""Tests for external provider-neutral capability discovery."""

from typing import cast
from unittest.mock import MagicMock

from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from trussium.api.capabilities import router as capabilities_router
from trussium.app import create_application
from trussium.capabilities import (
    CHAT_CAPABILITY_METADATA,
    CHAT_CAPABILITY_NAME,
    CapabilityAvailability,
    CapabilityAvailabilityStatus,
    CapabilityHealth,
    CapabilityHealthStatus,
    CapabilityMetadata,
    CapabilityRegistry,
)
from trussium.capabilities.chat import ChatCapability


class AvailabilityCapability:
    """Capability with the optional availability contract."""

    def __init__(self, availability: CapabilityAvailability) -> None:
        self.availability = availability
        self.calls = 0

    async def check_availability(self) -> CapabilityAvailability:
        """Return the configured bounded state."""
        self.calls += 1
        return self.availability


class HealthCapability:
    """Capability with the optional health contract."""

    def __init__(self, health: CapabilityHealth) -> None:
        self.health = health
        self.calls = 0

    async def check_health(self) -> CapabilityHealth:
        """Return the configured bounded state."""
        self.calls += 1
        return self.health


def test_empty_application_returns_stable_empty_availability() -> None:
    """Provider-free startup should report an available empty aggregate."""
    response = TestClient(create_application()).get("/v1/capabilities/availability")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "available", "capabilities": []}


def test_availability_reports_checks_and_defaults_in_registration_order() -> None:
    """Optional checks and ordinary registrations should share ordered reporting."""
    checked = AvailabilityCapability(
        CapabilityAvailability(
            name="future.embeddings",
            status=CapabilityAvailabilityStatus.UNAVAILABLE,
            reason="provider_offline",
        )
    )
    source = CapabilityRegistry()
    source.register("future.embeddings", checked)
    source.register("future.images", object())
    app = create_application(capability_registry=source)

    response = TestClient(app).get("/v1/capabilities/availability")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "status": "unavailable",
        "capabilities": [
            {
                "name": "future.embeddings",
                "status": "unavailable",
                "reason": "provider_offline",
            },
            {"name": "future.images", "status": "available"},
        ],
    }
    assert checked.calls == 1
    assert app.state.capability_availability_reporter.registry is source


def test_external_application_without_reporter_returns_empty_availability() -> None:
    """Direct router composition should retain a safe compatibility fallback."""
    app = FastAPI()
    app.include_router(capabilities_router)

    response = TestClient(app).get("/v1/capabilities/availability")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "available", "capabilities": []}


def test_empty_application_returns_stable_empty_capability_health() -> None:
    """Provider-free startup should report an ok empty health aggregate."""
    response = TestClient(create_application()).get("/v1/capabilities/health")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok", "capabilities": []}


def test_capability_health_is_ordered_and_independent_from_availability() -> None:
    """Health checks should not change availability or execution contracts."""
    checked = HealthCapability(
        CapabilityHealth(
            name="future.embeddings",
            status=CapabilityHealthStatus.DEGRADED,
            reason="warming",
        )
    )
    source = CapabilityRegistry()
    source.register("future.embeddings", checked)
    source.register("future.images", object())
    app = create_application(capability_registry=source)

    response = TestClient(app).get("/v1/capabilities/health")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "status": "degraded",
        "capabilities": [
            {"name": "future.embeddings", "status": "degraded", "reason": "warming"},
            {
                "name": "future.images",
                "status": "unknown",
                "reason": "capability_health_not_reported",
            },
        ],
    }
    assert checked.calls == 1
    assert app.state.capability_health_reporter.registry is source


def test_external_application_without_reporter_returns_empty_capability_health() -> None:
    """Direct router composition should retain a safe compatibility fallback."""
    app = FastAPI()
    app.include_router(capabilities_router)

    response = TestClient(app).get("/v1/capabilities/health")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok", "capabilities": []}


def test_empty_application_returns_stable_empty_discovery() -> None:
    """Provider-free runtime startup should expose an ordered empty collection."""
    response = TestClient(create_application()).get("/v1/capabilities")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"capabilities": []}


def test_discovery_returns_application_owned_metadata_in_registry_order() -> None:
    """The endpoint should expose metadata without implementation details or probing."""
    unknown_capability = object()
    unknown_metadata = CapabilityMetadata(
        name="future.embeddings",
        version="v2",
        description="Create normalized embeddings.",
        supports_streaming=False,
    )
    chat_capability = cast(ChatCapability, MagicMock(spec=ChatCapability))
    source = CapabilityRegistry()
    source.register("future.embeddings", unknown_capability, metadata=unknown_metadata)
    source.register(CHAT_CAPABILITY_NAME, chat_capability)
    app = create_application(capability_registry=source)

    response = TestClient(app).get("/v1/capabilities")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "capabilities": [
            {
                "name": "future.embeddings",
                "version": "v2",
                "description": "Create normalized embeddings.",
                "supports_streaming": False,
            },
            {
                "name": "chat.completions",
                "version": "v1",
                "description": "Create normalized provider-neutral chat completions.",
                "supports_streaming": True,
            },
        ]
    }
    assert source.sealed is True
    assert app.state.capability_registry.metadata == (
        unknown_metadata,
        CHAT_CAPABILITY_METADATA,
    )
    assert all("provider" not in capability for capability in response.json()["capabilities"])
    assert all("model" not in capability for capability in response.json()["capabilities"])
    assert all("implementation" not in capability for capability in response.json()["capabilities"])
    assert "MagicMock" not in response.text


def test_minimal_metadata_omits_unknown_optional_fields() -> None:
    """Legacy future registrations should disclose only their validated name."""
    registry = CapabilityRegistry()
    registry.register("future.images", object())

    response = TestClient(create_application(capability_registry=registry)).get("/v1/capabilities")

    assert response.json() == {"capabilities": [{"name": "future.images"}]}


def test_external_application_without_registry_returns_empty_discovery() -> None:
    """Direct FastAPI composition should retain a safe compatibility fallback."""
    app = FastAPI()
    app.include_router(capabilities_router)

    response = TestClient(app).get("/v1/capabilities")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"capabilities": []}


def test_discovery_is_documented_in_openapi() -> None:
    """Clients should be able to discover the stable response schema."""
    schema = create_application().openapi()

    operation = schema["paths"]["/v1/capabilities"]["get"]
    assert operation["summary"] == "Discover configured capabilities"
    assert operation["tags"] == ["capabilities"]
    assert "CapabilityDiscoveryResponse" in schema["components"]["schemas"]


def test_availability_is_documented_in_openapi() -> None:
    """Clients should be able to discover the stable availability schema."""
    schema = create_application().openapi()

    operation = schema["paths"]["/v1/capabilities/availability"]["get"]
    assert operation["summary"] == "Report capability availability"
    assert operation["tags"] == ["capabilities"]
    assert "CapabilityAvailabilityReportResponse" in schema["components"]["schemas"]


def test_capability_health_is_documented_in_openapi() -> None:
    """Clients should be able to discover the stable health schema."""
    schema = create_application().openapi()

    operation = schema["paths"]["/v1/capabilities/health"]["get"]
    assert operation["summary"] == "Report capability health"
    assert operation["tags"] == ["capabilities"]
    assert "CapabilityHealthReportResponse" in schema["components"]["schemas"]
