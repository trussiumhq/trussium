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
    guide = (_REPOSITORY_ROOT / "docs" / "HEALTH.md").read_text(encoding="utf-8")

    assert set(responses) >= {"200", "503"}
    assert "ReadinessResponse" in str(responses["200"])
    assert "ReadinessResponse" in str(responses["503"])
    assert "ReadinessResponse" not in str(liveness_responses["200"])

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
