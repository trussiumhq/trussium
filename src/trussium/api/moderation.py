"""Moderation API endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from trussium.api.dependencies import get_capability_execution_pipeline
from trussium.api.errors import capability_error_status_code
from trussium.capabilities.errors import CapabilityExecutionError
from trussium.capabilities.execution import CapabilityExecutionPipeline
from trussium.capabilities.moderation import (
    MODERATION_CAPABILITY_NAME,
    ModerationCapability,
    ModerationRequest,
    ModerationResponse,
)
from trussium.capabilities.registry import CapabilityContractMismatchError, CapabilityNotFoundError

router = APIRouter(prefix="/v1", tags=["moderation"])


@router.post("/moderations", response_model=ModerationResponse)
async def create_moderation(
    request: ModerationRequest,
    pipeline: Annotated[CapabilityExecutionPipeline, Depends(get_capability_execution_pipeline)],
) -> JSONResponse:
    try:
        response = await pipeline.execute(
            MODERATION_CAPABILITY_NAME,
            lambda capability: _require(capability).moderate(request),
            model=request.model,
        )
    except CapabilityNotFoundError as error:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "moderation_capability_unavailable",
                "message": "No moderation provider is configured.",
            },
        ) from error
    except CapabilityExecutionError as error:
        raise HTTPException(
            status_code=capability_error_status_code(error.category),
            detail={"code": error.code, "message": error.message},
        ) from error
    return JSONResponse(status_code=200, content=response.model_dump(mode="json"))


def _require(capability: object) -> ModerationCapability:
    if not isinstance(capability, ModerationCapability):
        raise CapabilityContractMismatchError(MODERATION_CAPABILITY_NAME)
    return capability
