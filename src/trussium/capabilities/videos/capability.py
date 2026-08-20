"""Video job capability interface."""

from typing import Final, Protocol, runtime_checkable

from trussium.capabilities.metadata import CapabilityMetadata
from trussium.capabilities.videos.models import VideoCreateRequest, VideoJob

VIDEO_CAPABILITY_NAME: Final = "videos"
VIDEO_CAPABILITY_METADATA: Final = CapabilityMetadata(
    name=VIDEO_CAPABILITY_NAME,
    version="v1",
    description="Create and retrieve normalized video jobs.",
    supports_streaming=False,
)


@runtime_checkable
class VideoCapability(Protocol):
    async def create(self, request: VideoCreateRequest) -> VideoJob: ...
    async def retrieve(self, video_id: str) -> VideoJob: ...
