"""Reranking API endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from trussium.api.dependencies import get_capability_execution_pipeline
from trussium.api.errors import capability_error_status_code
from trussium.capabilities.errors import CapabilityExecutionError
from trussium.capabilities.execution import CapabilityExecutionPipeline
from trussium.capabilities.registry import CapabilityContractMismatchError, CapabilityNotFoundError
from trussium.capabilities.reranking import (
    RERANKING_CAPABILITY_NAME,
    RerankingCapability,
    RerankingRequest,
    RerankingResponse,
)

router = APIRouter(prefix="/v1", tags=["rerankings"])


@router.post("/rerankings", response_model=RerankingResponse)
async def create_reranking(
    request: RerankingRequest,
    pipeline: Annotated[CapabilityExecutionPipeline, Depends(get_capability_execution_pipeline)],
) -> RerankingResponse:
    try:
        return await pipeline.execute(
            RERANKING_CAPABILITY_NAME,
            lambda capability: _require(capability).rerank(request),
            model=request.model,
        )
    except CapabilityNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "reranking_capability_unavailable",
                "message": "No reranking provider is configured.",
            },
        ) from error
    except CapabilityExecutionError as error:
        raise HTTPException(
            status_code=capability_error_status_code(error.category),
            detail={"code": error.code, "message": error.message},
        ) from error


def _require(capability: object) -> RerankingCapability:
    if not isinstance(capability, RerankingCapability):
        raise CapabilityContractMismatchError(RERANKING_CAPABILITY_NAME)
    return capability
