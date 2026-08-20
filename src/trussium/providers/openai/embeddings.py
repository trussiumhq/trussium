"""OpenAI-compatible embeddings capability adapter."""

from uuid import uuid4

from openai import APIError, AsyncOpenAI

from trussium.capabilities.embeddings import (
    EmbeddingInput,
    EmbeddingsRequest,
    EmbeddingsResponse,
    EmbeddingsUsage,
)
from trussium.observability.propagation import outbound_trace_context_headers
from trussium.providers.openai.chat import OpenAIChatCapability, OpenAIProviderError


class OpenAIEmbeddingsCapability:
    """OpenAI-compatible implementation of normalized embeddings."""

    provider_name = "openai"

    def __init__(self, client: AsyncOpenAI) -> None:
        self._client = client

    async def embed(self, request: EmbeddingsRequest) -> EmbeddingsResponse:
        """Execute and normalize one embeddings request."""
        try:
            response = await self._client.embeddings.create(
                model=request.model,
                input=request.input,
                encoding_format="float",
                extra_headers=outbound_trace_context_headers(),
            )
        except APIError as error:
            raise OpenAIChatCapability._normalize_api_error(error) from error

        data = [
            EmbeddingInput(index=item.index, embedding=item.embedding) for item in response.data
        ]
        if not data:
            raise OpenAIProviderError("OpenAI returned an embeddings response without data")

        usage = response.usage
        if usage is None:
            raise OpenAIProviderError("OpenAI returned an embeddings response without usage")

        return EmbeddingsResponse(
            id=str(uuid4()),
            provider=self.provider_name,
            model=str(response.model),
            data=data,
            usage=EmbeddingsUsage(
                input_tokens=usage.prompt_tokens,
                total_tokens=usage.total_tokens,
            ),
        )
