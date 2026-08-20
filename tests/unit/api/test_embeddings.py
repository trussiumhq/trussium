"""Tests for the provider-neutral embeddings endpoint."""

from fastapi import status
from fastapi.testclient import TestClient

from trussium.app import create_application
from trussium.capabilities import (
    EMBEDDINGS_CAPABILITY_METADATA,
    EMBEDDINGS_CAPABILITY_NAME,
    CapabilityRegistry,
)
from trussium.capabilities.embeddings import (
    EmbeddingInput,
    EmbeddingsRequest,
    EmbeddingsResponse,
    EmbeddingsUsage,
)


class StubEmbeddingsCapability:
    async def embed(self, request: EmbeddingsRequest) -> EmbeddingsResponse:
        return EmbeddingsResponse(
            id="embeddings-test-1",
            provider="stub",
            model=request.model,
            data=[
                EmbeddingInput(index=index, embedding=[float(index), 1.0])
                for index, _ in enumerate(request.input)
            ],
            usage=EmbeddingsUsage(input_tokens=3, total_tokens=3),
        )


def test_embeddings_returns_normalized_response() -> None:
    registry = CapabilityRegistry()
    registry.register(
        EMBEDDINGS_CAPABILITY_NAME,
        StubEmbeddingsCapability(),
        metadata=EMBEDDINGS_CAPABILITY_METADATA,
    )

    response = TestClient(create_application(capability_registry=registry)).post(
        "/v1/embeddings",
        json={"model": "embedding-test", "input": ["one", "two"]},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "id": "embeddings-test-1",
        "provider": "stub",
        "model": "embedding-test",
        "data": [
            {"index": 0, "embedding": [0.0, 1.0]},
            {"index": 1, "embedding": [1.0, 1.0]},
        ],
        "usage": {"input_tokens": 3, "total_tokens": 3},
    }


def test_embeddings_without_registered_capability_is_unavailable() -> None:
    response = TestClient(create_application()).post(
        "/v1/embeddings",
        json={"model": "embedding-test", "input": ["one"]},
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {
        "detail": {
            "code": "embeddings_capability_unavailable",
            "message": "No embeddings provider is configured.",
        }
    }


def test_embeddings_contract_requires_nonempty_input() -> None:
    response = TestClient(create_application()).post(
        "/v1/embeddings",
        json={"model": "embedding-test", "input": []},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
