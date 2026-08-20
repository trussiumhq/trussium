"""OpenAI audio-transcription capability adapter."""

from typing import cast
from uuid import uuid4

from openai import APIError, AsyncOpenAI
from openai._types import omit

from trussium.capabilities.transcription import (
    TranscriptionRequest,
    TranscriptionResponse,
    TranscriptionSegment,
)
from trussium.observability.propagation import outbound_trace_context_headers
from trussium.providers.openai.chat import OpenAIChatCapability, OpenAIProviderError


class OpenAITranscriptionCapability:
    provider_name = "openai"

    def __init__(self, client: AsyncOpenAI) -> None:
        self._client = client

    async def transcribe(self, request: TranscriptionRequest) -> TranscriptionResponse:
        try:
            response = await self._client.audio.transcriptions.create(
                file=(
                    request.audio.filename,
                    request.audio.data,
                    request.audio.content_type or "application/octet-stream",
                ),
                model=request.model,
                language=request.language if request.language is not None else omit,
                prompt=request.prompt if request.prompt is not None else omit,
                temperature=request.temperature if request.temperature is not None else omit,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
                extra_headers=outbound_trace_context_headers(),
            )
        except APIError as error:
            raise OpenAIChatCapability._normalize_api_error(error) from error
        text = cast(str | None, getattr(response, "text", None))
        if not text:
            raise OpenAIProviderError("OpenAI returned a transcription response without text")
        segments = [
            TranscriptionSegment(
                id=segment.id,
                start=segment.start,
                end=segment.end,
                text=segment.text,
            )
            for segment in (getattr(response, "segments", None) or [])
        ]
        return TranscriptionResponse(
            id=str(uuid4()),
            provider=self.provider_name,
            model=request.model,
            text=text,
            language=cast(str | None, getattr(response, "language", None)),
            duration=cast(float | None, getattr(response, "duration", None)),
            segments=segments,
        )
