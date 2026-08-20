"""Video job API endpoints."""

from collections.abc import Callable, Coroutine
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from trussium.api.dependencies import get_capability_execution_pipeline
from trussium.api.errors import capability_error_status_code
from trussium.capabilities.errors import CapabilityExecutionError
from trussium.capabilities.execution import CapabilityExecutionPipeline
from trussium.capabilities.registry import CapabilityContractMismatchError, CapabilityNotFoundError
from trussium.capabilities.videos import (
    VIDEO_CAPABILITY_NAME,
    VideoCapability,
    VideoCreateRequest,
    VideoJob,
)

router = APIRouter(prefix="/v1", tags=["videos"])
VideoOperation = Callable[[object], Coroutine[object, object, VideoJob]]


@router.post("/videos", response_model=VideoJob)
async def create_video(
    request: VideoCreateRequest,
    pipeline: Annotated[CapabilityExecutionPipeline, Depends(get_capability_execution_pipeline)],
) -> VideoJob:
    return await _execute(
        pipeline, lambda capability: _require(capability).create(request), request.model
    )


@router.get("/videos/{video_id}", response_model=VideoJob)
async def get_video(
    video_id: str,
    pipeline: Annotated[CapabilityExecutionPipeline, Depends(get_capability_execution_pipeline)],
) -> VideoJob:
    return await _execute(
        pipeline, lambda capability: _require(capability).retrieve(video_id), None
    )


async def _execute(
    pipeline: CapabilityExecutionPipeline, operation: VideoOperation, model: str | None
) -> VideoJob:
    try:
        return await pipeline.execute(VIDEO_CAPABILITY_NAME, operation, model=model)
    except CapabilityNotFoundError as error:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "video_capability_unavailable",
                "message": "No video provider is configured.",
            },
        ) from error
    except CapabilityExecutionError as error:
        raise HTTPException(
            status_code=capability_error_status_code(error.category),
            detail={"code": error.code, "message": error.message},
        ) from error


def _require(capability: object) -> VideoCapability:
    if not isinstance(capability, VideoCapability):
        raise CapabilityContractMismatchError(VIDEO_CAPABILITY_NAME)
    return capability
