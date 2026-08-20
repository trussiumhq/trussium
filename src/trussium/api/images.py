"""Image-generation API endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from trussium.api.dependencies import get_capability_execution_pipeline
from trussium.api.errors import capability_error_status_code
from trussium.capabilities.errors import CapabilityExecutionError
from trussium.capabilities.execution import CapabilityExecutionPipeline
from trussium.capabilities.images import (
    IMAGE_GENERATION_CAPABILITY_NAME,
    ImageGenerationCapability,
    ImageGenerationRequest,
    ImageGenerationResponse,
)
from trussium.capabilities.registry import CapabilityContractMismatchError, CapabilityNotFoundError

router = APIRouter(prefix="/v1", tags=["images"])


@router.post("/images/generations", response_model=ImageGenerationResponse)
async def create_image(
    request: ImageGenerationRequest,
    pipeline: Annotated[CapabilityExecutionPipeline, Depends(get_capability_execution_pipeline)],
) -> JSONResponse:
    try:
        response = await pipeline.execute(
            IMAGE_GENERATION_CAPABILITY_NAME,
            lambda capability: _require(capability).generate(request),
            model=request.model,
        )
    except CapabilityNotFoundError as error:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "image_generation_capability_unavailable",
                "message": "No image-generation provider is configured.",
            },
        ) from error
    except CapabilityExecutionError as error:
        raise HTTPException(
            status_code=capability_error_status_code(error.category),
            detail={"code": error.code, "message": error.message},
        ) from error
    return JSONResponse(status_code=200, content=response.model_dump(mode="json"))


def _require(capability: object) -> ImageGenerationCapability:
    if not isinstance(capability, ImageGenerationCapability):
        raise CapabilityContractMismatchError(IMAGE_GENERATION_CAPABILITY_NAME)
    return capability
