"""Tests for batch inference endpoints."""

from fastapi.testclient import TestClient

from trussium.app import create_application
from trussium.capabilities import CapabilityRegistry
from trussium.capabilities.batches import (
    BATCHES_CAPABILITY_METADATA,
    BATCHES_CAPABILITY_NAME,
    BatchCreateRequest,
    BatchJob,
)


class StubBatchCapability:
    async def create(self, request: BatchCreateRequest) -> BatchJob:
        return BatchJob(
            id="batch-1",
            provider="stub",
            status="validating",
            endpoint=request.endpoint,
            input_file_id=request.input_file_id,
        )

    async def retrieve(self, batch_id: str) -> BatchJob:
        return BatchJob(
            id=batch_id,
            provider="stub",
            status="completed",
            endpoint="/v1/chat/completions",
            input_file_id="file-in",
            output_file_id="file-out",
        )

    async def cancel(self, batch_id: str) -> BatchJob:
        return BatchJob(
            id=batch_id,
            provider="stub",
            status="cancelling",
            endpoint="/v1/chat/completions",
            input_file_id="file-in",
        )


def test_batch_job_lifecycle() -> None:
    registry = CapabilityRegistry()
    registry.register(
        BATCHES_CAPABILITY_NAME, StubBatchCapability(), metadata=BATCHES_CAPABILITY_METADATA
    )
    client = TestClient(create_application(capability_registry=registry))
    assert client.post("/v1/batches", json={"input_file_id": "file-in"}).json()["id"] == "batch-1"
    assert client.get("/v1/batches/batch-1").json()["output_file_id"] == "file-out"
    assert client.post("/v1/batches/batch-1/cancel").json()["status"] == "cancelling"


def test_batches_are_unavailable_without_a_registered_provider() -> None:
    response = TestClient(create_application()).post(
        "/v1/batches", json={"input_file_id": "file-in"}
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "batch_capability_unavailable"
