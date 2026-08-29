"""Embeddings API endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from trussium.api.dependencies import get_capability_execution_pipeline
from trussium.api.errors import capability_error_status_code
from trussium.capabilities.embeddings import (
    EMBEDDINGS_CAPABILITY_NAME,
    EmbeddingsCapability,
    EmbeddingsRequest,
    EmbeddingsResponse,
)
from trussium.capabilities.errors import CapabilityExecutionError
from trussium.capabilities.execution import CapabilityExecutionPipeline
from trussium.capabilities.registry import CapabilityContractMismatchError, CapabilityNotFoundError
from trussium.runtime import UsageMeter, UsageQuotaExceededError

router = APIRouter(prefix="/v1", tags=["embeddings"])


@router.post("/embeddings", response_model=EmbeddingsResponse, status_code=status.HTTP_200_OK)
async def create_embeddings(
    request: EmbeddingsRequest,
    http_request: Request,
    pipeline: Annotated[CapabilityExecutionPipeline, Depends(get_capability_execution_pipeline)],
) -> JSONResponse:
    """Create normalized text embeddings."""
    try:
        response = await pipeline.execute(
            EMBEDDINGS_CAPABILITY_NAME,
            lambda capability: _require_embeddings_capability(capability).embed(request),
            model=request.model,
        )
    except CapabilityNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "embeddings_capability_unavailable",
                "message": "No embeddings provider is configured.",
            },
        ) from error
    except CapabilityExecutionError as error:
        raise HTTPException(
            status_code=capability_error_status_code(error.category),
            detail={"code": error.code, "message": error.message},
        ) from error

    usage_meter = getattr(http_request.app.state, "usage_meter", None)
    if isinstance(usage_meter, UsageMeter):
        try:
            usage_meter.record(
                input_tokens=response.usage.input_tokens,
                total_tokens=response.usage.total_tokens,
            )
        except UsageQuotaExceededError as error:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"code": "usage_quota_exceeded", "message": "Usage quota exceeded."},
            ) from error

    return JSONResponse(status_code=status.HTTP_200_OK, content=response.model_dump(mode="json"))


def _require_embeddings_capability(capability: object) -> EmbeddingsCapability:
    if not isinstance(capability, EmbeddingsCapability):
        raise CapabilityContractMismatchError(EMBEDDINGS_CAPABILITY_NAME)
    return capability
