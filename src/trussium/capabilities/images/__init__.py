"""Provider-neutral image-generation capability contracts."""

from trussium.capabilities.images.capability import (
    IMAGE_GENERATION_CAPABILITY_METADATA,
    IMAGE_GENERATION_CAPABILITY_NAME,
    ImageGenerationCapability,
)
from trussium.capabilities.images.models import (
    GeneratedImage,
    ImageGenerationRequest,
    ImageGenerationResponse,
)

__all__ = [
    "IMAGE_GENERATION_CAPABILITY_METADATA",
    "IMAGE_GENERATION_CAPABILITY_NAME",
    "GeneratedImage",
    "ImageGenerationCapability",
    "ImageGenerationRequest",
    "ImageGenerationResponse",
]
