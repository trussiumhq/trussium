"""Tests for runtime health endpoints."""

from pathlib import Path

from fastapi import status
from fastapi.testclient import TestClient

from trussium.app import create_application
from trussium.config import ReadinessSettings, Settings
from trussium.runtime import (
    DependencyFailureReason,
    DependencyHealth,
    DependencyStatus,
    RuntimeComponentHealth,
    RuntimeComponentStatus,
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class StubHealthCheck:
    """Return a configured bounded dependency result."""

    name = "provider"
    provider = "openai"
    model = "required-model"

    def __init__(self, result: DependencyHealth) -> None:
        """Initialize the check result."""
        self.result = result
        self.calls = 0
        self.closed = False

    async def check(self) -> DependencyHealth:
        """Return the configured dependency result."""
        self.calls += 1
        return self.result

    async def close(self) -> None:
        """Record application-lifespan cleanup."""
        self.closed = True


class StubRuntimeService:
    """Application-scoped service without component health reporting."""

    def __init__(self, name: str) -> None:
        """Store the stable service name."""
        self.name = name

    async def startup(self) -> None:
        """Implement lifecycle startup."""

    async def shutdown(self) -> None:
        """Implement lifecycle shutdown."""


class ReportingRuntimeService(StubRuntimeService):
    """Application-scoped service returning a bounded component state."""

    def __init__(self, health: RuntimeComponentHealth) -> None:
        """Store the configured component state."""
        super().__init__(health.name)
        self.health = health
        self.calls = 0

    async def check_health(self) -> RuntimeComponentHealth:
        """Return the configured component state."""
        self.calls += 1
        return self.health


def test_liveness_endpoint_returns_ok() -> None:
    """The liveness endpoint should report a running runtime."""
    client = TestClient(create_application())

    response = client.get("/health/live")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}


def test_readiness_endpoint_returns_ok() -> None:
    """The readiness endpoint should report a ready runtime."""
    client = TestClient(create_application())

    response = client.get("/health/ready")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}


def test_component_health_endpoint_returns_empty_ok_report() -> None:
    """An empty registry should have a stable informational response."""
    client = TestClient(create_application())

    response = client.get("/health/components")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok", "components": []}


def test_component_health_reports_registry_order_without_changing_probes() -> None:
    """Component severity should remain independent from liveness and readiness."""
    healthy = ReportingRuntimeService(
        RuntimeComponentHealth(name="healthy", status=RuntimeComponentStatus.OK)
    )
    unreported = StubRuntimeService("unreported")
    degraded = ReportingRuntimeService(
        RuntimeComponentHealth(
            name="degraded",
            status=RuntimeComponentStatus.DEGRADED,
            reason="cache_warming",
        )
    )
    client = TestClient(create_application(runtime_services=(healthy, unreported, degraded)))

    response = client.get("/health/components")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "status": "degraded",
        "components": [
            {"name": "healthy", "status": "ok"},
            {
                "name": "unreported",
                "status": "unknown",
                "reason": "component_health_not_reported",
            },
            {
                "name": "degraded",
                "status": "degraded",
                "reason": "cache_warming",
            },
        ],
    }
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ok"}
    assert healthy.calls == degraded.calls == 1


def test_unavailable_component_report_remains_http_200() -> None:
    """Component reporting must never become an implicit readiness gate."""
    unavailable = ReportingRuntimeService(
        RuntimeComponentHealth(
            name="database",
            status=RuntimeComponentStatus.UNAVAILABLE,
            reason="connection_unavailable",
        )
    )
    client = TestClient(create_application(runtime_services=(unavailable,)))

    response = client.get("/health/components")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "status": "unavailable",
        "components": [
            {
                "name": "database",
                "status": "unavailable",
                "reason": "connection_unavailable",
            }
        ],
    }
    assert client.get("/health/live").status_code == status.HTTP_200_OK
    assert client.get("/health/ready").status_code == status.HTTP_200_OK


def test_enabled_dependency_readiness_returns_bounded_success_and_caches() -> None:
    """A healthy dependency should return bounded details without repeated calls."""
    check = StubHealthCheck(
        DependencyHealth(
            name="provider",
            status=DependencyStatus.OK,
            provider="openai",
            model="required-model",
        )
    )
    settings = Settings(
        readiness=ReadinessSettings(dependency_checks_enabled=True),
    )

    with TestClient(create_application(settings=settings, dependency_health_check=check)) as client:
        first = client.get("/health/ready")
        second = client.get("/health/ready")

    assert first.status_code == status.HTTP_200_OK
    assert first.json() == {
        "status": "ok",
        "dependencies": [
            {
                "name": "provider",
                "status": "ok",
                "provider": "openai",
                "model": "required-model",
            }
        ],
    }
    assert second.json() == first.json()
    assert check.calls == 1
    assert check.closed is True


def test_unavailable_dependency_returns_503_without_raw_failure_data() -> None:
    """Readiness failures should expose only the stable dependency contract."""
    check = StubHealthCheck(
        DependencyHealth(
            name="provider",
            status=DependencyStatus.UNAVAILABLE,
            provider="ollama",
            model=None,
            reason=DependencyFailureReason.PROVIDER_UNREACHABLE,
        )
    )
    settings = Settings(
        readiness=ReadinessSettings(dependency_checks_enabled=True),
    )
    client = TestClient(create_application(settings=settings, dependency_health_check=check))

    response = client.get("/health/ready")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {
        "status": "unavailable",
        "dependencies": [
            {
                "name": "provider",
                "status": "unavailable",
                "provider": "ollama",
                "reason": "provider_unreachable",
            }
        ],
    }
    assert "endpoint" not in response.text.lower()
    assert "credential" not in response.text.lower()


def test_liveness_stays_ok_when_dependency_is_unavailable() -> None:
    """External dependency failure must never turn process liveness into failure."""
    check = StubHealthCheck(
        DependencyHealth(
            name="provider",
            status=DependencyStatus.UNAVAILABLE,
            provider="openai",
            reason=DependencyFailureReason.PROVIDER_AUTHENTICATION_FAILED,
        )
    )
    settings = Settings(
        readiness=ReadinessSettings(dependency_checks_enabled=True),
    )
    client = TestClient(create_application(settings=settings, dependency_health_check=check))

    assert client.get("/health/live").json() == {"status": "ok"}
    assert check.calls == 0


def test_openapi_and_health_guide_publish_the_complete_readiness_contract() -> None:
    """Operators should receive the response, configuration, and privacy contract."""
    client = TestClient(create_application())
    openapi = client.get("/openapi.json").json()
    responses = openapi["paths"]["/health/ready"]["get"]["responses"]
    liveness_responses = openapi["paths"]["/health/live"]["get"]["responses"]
    component_responses = openapi["paths"]["/health/components"]["get"]["responses"]
    guide = (_REPOSITORY_ROOT / "docs" / "HEALTH.md").read_text(encoding="utf-8")

    assert set(responses) >= {"200", "503"}
    assert "ReadinessResponse" in str(responses["200"])
    assert "ReadinessResponse" in str(responses["503"])
    assert "ReadinessResponse" not in str(liveness_responses["200"])
    assert set(component_responses) == {"200"}
    assert "ComponentHealthReportResponse" in str(component_responses["200"])

    for setting in (
        "TRUSSIUM_READINESS__DEPENDENCY_CHECKS_ENABLED",
        "TRUSSIUM_READINESS__DEPENDENCY_TIMEOUT_SECONDS",
        "TRUSSIUM_READINESS__DEPENDENCY_CACHE_SECONDS",
        "TRUSSIUM_READINESS__REQUIRED_MODEL",
    ):
        assert setting in guide

    for reason in DependencyFailureReason:
        assert f"`{reason.value}`" in guide

    assert "never calls a provider" in guide
    assert "Neither mode\nsends a prompt, requests inference" in guide
    assert "credentials, provider\nor proxy endpoints" in guide
    assert "single refresh rather than fanning out provider calls" in guide


def test_component_health_guide_publishes_status_timeout_and_probe_boundaries() -> None:
    """Component operators should receive the complete informational contract."""
    guide = (_REPOSITORY_ROOT / "docs" / "COMPONENT_HEALTH.md").read_text(encoding="utf-8")

    assert "TRUSSIUM_RUNTIME__COMPONENT_HEALTH_TIMEOUT_SECONDS" in guide
    for component_status in RuntimeComponentStatus:
        assert f"`{component_status.value}`" in guide
    for reason in (
        "component_health_not_reported",
        "component_health_timeout",
        "component_health_check_failed",
    ):
        assert f"`{reason}`" in guide

    assert "always http 200" in guide.lower()
    assert "not a startup, liveness, or readiness probe" in guide
    assert "Native `asyncio.CancelledError` always propagates" in guide
