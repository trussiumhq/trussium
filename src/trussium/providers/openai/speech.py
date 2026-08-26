"""OpenAI text-to-speech capability adapter."""

import base64
from uuid import uuid4

from openai import APIError, AsyncOpenAI

from trussium.capabilities.speech import SpeechRequest, SpeechResponse
from trussium.observability.propagation import outbound_trace_context_headers
from trussium.providers.openai.chat import OpenAIChatCapability, OpenAIProviderError


class OpenAISpeechCapability:
    """Normalize OpenAI audio speech responses into Trussium contracts."""

    provider_name = "openai"

    def __init__(self, client: AsyncOpenAI) -> None:
        self._client = client

    async def synthesize(self, request: SpeechRequest) -> SpeechResponse:
        try:
            response = await self._client.audio.speech.create(
                model=request.model,
                input=request.input,
                voice=request.voice,
                response_format=request.response_format,
                speed=request.speed,
                extra_headers=outbound_trace_context_headers(),
            )
            audio = await response.aread()
        except APIError as error:
            raise OpenAIChatCapability._normalize_api_error(error) from error
        except Exception as error:
            raise OpenAIProviderError("OpenAI returned an invalid speech response") from error
        if not audio:
            raise OpenAIProviderError("OpenAI returned an empty speech response")
        return SpeechResponse(
            id=f"speech-{uuid4().hex}",
            provider=self.provider_name,
            model=request.model,
            audio=base64.b64encode(audio).decode("ascii"),
            response_format=request.response_format,
        )
