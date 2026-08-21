"""Batch inference job endpoints."""

from collections.abc import Callable, Coroutine
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from trussium.api.dependencies import get_capability_execution_pipeline
from trussium.api.errors import capability_error_status_code
from trussium.capabilities.batches import (
    BATCHES_CAPABILITY_NAME,
    BatchCapability,
    BatchCreateRequest,
    BatchJob,
)
from trussium.capabilities.errors import CapabilityExecutionError
from trussium.capabilities.execution import CapabilityExecutionPipeline
from trussium.capabilities.registry import CapabilityContractMismatchError, CapabilityNotFoundError

router = APIRouter(prefix="/v1", tags=["batches"])
BatchOperation = Callable[[object], Coroutine[object, object, BatchJob]]


@router.post("/batches", response_model=BatchJob)
async def create_batch(
    request: BatchCreateRequest,
    pipeline: Annotated[CapabilityExecutionPipeline, Depends(get_capability_execution_pipeline)],
) -> BatchJob:
    return await _execute(pipeline, lambda capability: _require(capability).create(request))


@router.get("/batches/{batch_id}", response_model=BatchJob)
async def get_batch(
    batch_id: str,
    pipeline: Annotated[CapabilityExecutionPipeline, Depends(get_capability_execution_pipeline)],
) -> BatchJob:
    return await _execute(pipeline, lambda capability: _require(capability).retrieve(batch_id))


@router.post("/batches/{batch_id}/cancel", response_model=BatchJob)
async def cancel_batch(
    batch_id: str,
    pipeline: Annotated[CapabilityExecutionPipeline, Depends(get_capability_execution_pipeline)],
) -> BatchJob:
    return await _execute(pipeline, lambda capability: _require(capability).cancel(batch_id))


async def _execute(pipeline: CapabilityExecutionPipeline, operation: BatchOperation) -> BatchJob:
    try:
        return await pipeline.execute(BATCHES_CAPABILITY_NAME, operation)
    except CapabilityNotFoundError as error:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "batch_capability_unavailable",
                "message": "No batch provider is configured.",
            },
        ) from error
    except CapabilityExecutionError as error:
        raise HTTPException(
            status_code=capability_error_status_code(error.category),
            detail={"code": error.code, "message": error.message},
        ) from error


def _require(capability: object) -> BatchCapability:
    if not isinstance(capability, BatchCapability):
        raise CapabilityContractMismatchError(BATCHES_CAPABILITY_NAME)
    return capability
