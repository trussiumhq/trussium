"""Tests for the provider-neutral moderation endpoint."""

from fastapi import status
from fastapi.testclient import TestClient

from trussium.app import create_application
from trussium.capabilities import (
    MODERATION_CAPABILITY_METADATA,
    MODERATION_CAPABILITY_NAME,
    CapabilityRegistry,
)
from trussium.capabilities.moderation import ModerationRequest, ModerationResponse, ModerationResult


class StubModerationCapability:
    async def moderate(self, request: ModerationRequest) -> ModerationResponse:
        return ModerationResponse(
            id="moderation-test-1",
            provider="stub",
            model=request.model,
            results=[
                ModerationResult(
                    flagged=False,
                    categories={"violence": False},
                    category_scores={"violence": 0.01},
                )
                for _ in request.input
            ],
        )


def test_moderation_returns_normalized_results() -> None:
    registry = CapabilityRegistry()
    registry.register(
        MODERATION_CAPABILITY_NAME,
        StubModerationCapability(),
        metadata=MODERATION_CAPABILITY_METADATA,
    )
    response = TestClient(create_application(capability_registry=registry)).post(
        "/v1/moderations", json={"model": "omni-moderation-latest", "input": ["safe"]}
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "id": "moderation-test-1",
        "provider": "stub",
        "model": "omni-moderation-latest",
        "results": [
            {
                "flagged": False,
                "categories": {"violence": False},
                "category_scores": {"violence": 0.01},
            }
        ],
    }


def test_moderation_without_registered_capability_is_unavailable() -> None:
    response = TestClient(create_application()).post(
        "/v1/moderations", json={"model": "omni-moderation-latest", "input": ["safe"]}
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["detail"]["code"] == "moderation_capability_unavailable"
