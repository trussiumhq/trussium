"""Image-generation capability provider interface."""

from typing import Final, Protocol, runtime_checkable

from trussium.capabilities.images.models import ImageGenerationRequest, ImageGenerationResponse
from trussium.capabilities.metadata import CapabilityMetadata

IMAGE_GENERATION_CAPABILITY_NAME: Final = "images.generations"
IMAGE_GENERATION_CAPABILITY_METADATA: Final = CapabilityMetadata(
    name=IMAGE_GENERATION_CAPABILITY_NAME,
    version="v1",
    description="Create normalized provider-neutral generated images.",
    supports_streaming=False,
)


@runtime_checkable
class ImageGenerationCapability(Protocol):
    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse: ...
