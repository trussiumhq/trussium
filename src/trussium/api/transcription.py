"""Audio-transcription API endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from trussium.api.dependencies import get_capability_execution_pipeline
from trussium.api.errors import capability_error_status_code
from trussium.capabilities.errors import CapabilityExecutionError
from trussium.capabilities.execution import CapabilityExecutionPipeline
from trussium.capabilities.registry import CapabilityContractMismatchError, CapabilityNotFoundError
from trussium.capabilities.transcription import (
    TRANSCRIPTION_CAPABILITY_NAME,
    AudioInput,
    TranscriptionCapability,
    TranscriptionRequest,
)

router = APIRouter(prefix="/v1", tags=["audio"])


@router.post("/audio/transcriptions")
async def create_transcription(
    file: Annotated[UploadFile, File()],
    model: Annotated[str, Form(min_length=1)],
    pipeline: Annotated[CapabilityExecutionPipeline, Depends(get_capability_execution_pipeline)],
    language: Annotated[str | None, Form(min_length=1)] = None,
    prompt: Annotated[str | None, Form(min_length=1)] = None,
    temperature: Annotated[float | None, Form(ge=0, le=1)] = None,
) -> JSONResponse:
    request = TranscriptionRequest(
        model=model,
        audio=AudioInput(
            filename=file.filename or "audio",
            content_type=file.content_type,
            data=await file.read(),
        ),
        language=language,
        prompt=prompt,
        temperature=temperature,
    )
    try:
        response = await pipeline.execute(
            TRANSCRIPTION_CAPABILITY_NAME,
            lambda capability: _require(capability).transcribe(request),
            model=request.model,
        )
    except CapabilityNotFoundError as error:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "transcription_capability_unavailable",
                "message": "No audio-transcription provider is configured.",
            },
        ) from error
    except CapabilityExecutionError as error:
        raise HTTPException(
            status_code=capability_error_status_code(error.category),
            detail={"code": error.code, "message": error.message},
        ) from error
    return JSONResponse(status_code=200, content=response.model_dump(mode="json"))


def _require(capability: object) -> TranscriptionCapability:
    if not isinstance(capability, TranscriptionCapability):
        raise CapabilityContractMismatchError(TRANSCRIPTION_CAPABILITY_NAME)
    return capability
