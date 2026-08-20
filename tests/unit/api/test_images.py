"""Tests for the provider-neutral image-generation endpoint."""

from fastapi.testclient import TestClient

from trussium.app import create_application
from trussium.capabilities import (
    IMAGE_GENERATION_CAPABILITY_METADATA,
    IMAGE_GENERATION_CAPABILITY_NAME,
    CapabilityRegistry,
)
from trussium.capabilities.images import (
    GeneratedImage,
    ImageGenerationRequest,
    ImageGenerationResponse,
)


class StubImageCapability:
    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        return ImageGenerationResponse(
            id="image-test-1",
            provider="stub",
            model=request.model,
            data=[GeneratedImage(b64_json="aW1hZ2U=")],
        )


def test_image_generation_returns_normalized_response() -> None:
    registry = CapabilityRegistry()
    registry.register(
        IMAGE_GENERATION_CAPABILITY_NAME,
        StubImageCapability(),
        metadata=IMAGE_GENERATION_CAPABILITY_METADATA,
    )
    response = TestClient(create_application(capability_registry=registry)).post(
        "/v1/images/generations", json={"model": "gpt-image-1", "prompt": "a tree"}
    )
    assert response.status_code == 200
    assert response.json()["data"] == [{"b64_json": "aW1hZ2U=", "revised_prompt": None}]


def test_image_generation_without_registered_capability_is_unavailable() -> None:
    response = TestClient(create_application()).post(
        "/v1/images/generations", json={"model": "gpt-image-1", "prompt": "a tree"}
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "image_generation_capability_unavailable"
