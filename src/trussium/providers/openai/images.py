"""OpenAI image-generation capability adapter."""

from uuid import uuid4

from openai import APIError, AsyncOpenAI

from trussium.capabilities.images import (
    GeneratedImage,
    ImageGenerationRequest,
    ImageGenerationResponse,
)
from trussium.observability.propagation import outbound_trace_context_headers
from trussium.providers.openai.chat import OpenAIChatCapability, OpenAIProviderError


class OpenAIImageGenerationCapability:
    provider_name = "openai"

    def __init__(self, client: AsyncOpenAI) -> None:
        self._client = client

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        try:
            response = await self._client.images.generate(
                model=request.model,
                prompt=request.prompt,
                n=request.count,
                size=request.size,
                extra_headers=outbound_trace_context_headers(),
            )
        except APIError as error:
            raise OpenAIChatCapability._normalize_api_error(error) from error
        source_data = response.data or []
        data = [
            GeneratedImage(b64_json=item.b64_json, revised_prompt=item.revised_prompt)
            for item in source_data
            if item.b64_json
        ]
        if not data:
            raise OpenAIProviderError("OpenAI returned an image response without image data")
        return ImageGenerationResponse(
            id=str(uuid4()), provider=self.provider_name, model=request.model, data=data
        )
