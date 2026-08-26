"""Text-to-speech API endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from trussium.api.dependencies import get_capability_execution_pipeline
from trussium.api.errors import capability_error_status_code
from trussium.capabilities.errors import CapabilityExecutionError
from trussium.capabilities.execution import CapabilityExecutionPipeline
from trussium.capabilities.registry import CapabilityContractMismatchError, CapabilityNotFoundError
from trussium.capabilities.speech import (
    SPEECH_CAPABILITY_NAME,
    SpeechCapability,
    SpeechRequest,
    SpeechResponse,
)

router = APIRouter(prefix="/v1", tags=["speech"])


@router.post("/audio/speech", response_model=SpeechResponse)
async def create_speech(
    request: SpeechRequest,
    pipeline: Annotated[CapabilityExecutionPipeline, Depends(get_capability_execution_pipeline)],
) -> JSONResponse:
    try:
        response = await pipeline.execute(
            SPEECH_CAPABILITY_NAME,
            lambda capability: _require(capability).synthesize(request),
            model=request.model,
        )
    except CapabilityNotFoundError as error:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "speech_capability_unavailable",
                "message": "No speech provider is configured.",
            },
        ) from error
    except CapabilityExecutionError as error:
        raise HTTPException(
            status_code=capability_error_status_code(error.category),
            detail={"code": error.code, "message": error.message},
        ) from error
    return JSONResponse(status_code=200, content=response.model_dump(mode="json"))


def _require(capability: object) -> SpeechCapability:
    if not isinstance(capability, SpeechCapability):
        raise CapabilityContractMismatchError(SPEECH_CAPABILITY_NAME)
    return capability
