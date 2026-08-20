"""Tests for the provider-neutral reranking endpoint."""

from fastapi.testclient import TestClient

from trussium.app import create_application
from trussium.capabilities import (
    RERANKING_CAPABILITY_METADATA,
    RERANKING_CAPABILITY_NAME,
    CapabilityRegistry,
)
from trussium.capabilities.reranking import RerankingRequest, RerankingResponse, RerankingResult


class StubRerankingCapability:
    async def rerank(self, request: RerankingRequest) -> RerankingResponse:
        return RerankingResponse(
            id="reranking-test-1",
            provider="tei",
            model=request.model,
            results=[RerankingResult(index=1, relevance_score=0.9)],
        )


def test_reranking_returns_normalized_response() -> None:
    registry = CapabilityRegistry()
    registry.register(
        RERANKING_CAPABILITY_NAME,
        StubRerankingCapability(),
        metadata=RERANKING_CAPABILITY_METADATA,
    )
    response = TestClient(create_application(capability_registry=registry)).post(
        "/v1/rerankings",
        json={
            "model": "bge-reranker",
            "query": "hello",
            "documents": [{"text": "one"}, {"text": "two"}],
        },
    )
    assert response.status_code == 200
    assert response.json()["results"] == [{"index": 1, "relevance_score": 0.9}]


def test_reranking_without_provider_is_unavailable() -> None:
    response = TestClient(create_application()).post(
        "/v1/rerankings",
        json={"model": "bge-reranker", "query": "hello", "documents": [{"text": "one"}]},
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "reranking_capability_unavailable"
