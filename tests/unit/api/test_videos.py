"""Tests for video job endpoints."""

from fastapi.testclient import TestClient

from trussium.app import create_application
from trussium.capabilities import (
    VIDEO_CAPABILITY_METADATA,
    VIDEO_CAPABILITY_NAME,
    CapabilityRegistry,
)
from trussium.capabilities.videos import VideoCreateRequest, VideoJob


class StubVideoCapability:
    async def create(self, request: VideoCreateRequest) -> VideoJob:
        return VideoJob(
            id="video-1", provider="stub", model=request.model, status="queued", progress=0
        )

    async def retrieve(self, video_id: str) -> VideoJob:
        return VideoJob(
            id=video_id, provider="stub", model="sora-2", status="completed", progress=100
        )


def test_video_job_create_and_retrieve() -> None:
    registry = CapabilityRegistry()
    registry.register(
        VIDEO_CAPABILITY_NAME, StubVideoCapability(), metadata=VIDEO_CAPABILITY_METADATA
    )
    client = TestClient(create_application(capability_registry=registry))
    assert (
        client.post("/v1/videos", json={"model": "sora-2", "prompt": "sunset"}).status_code == 200
    )
    assert client.get("/v1/videos/video-1").json()["status"] == "completed"
