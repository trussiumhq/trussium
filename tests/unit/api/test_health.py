"""Tests for runtime health endpoints."""

from fastapi import status
from fastapi.testclient import TestClient

from trussium.app import create_application


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
