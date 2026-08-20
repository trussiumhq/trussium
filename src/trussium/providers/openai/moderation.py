"""OpenAI moderation capability adapter."""

from openai import APIError, AsyncOpenAI

from trussium.capabilities.moderation import ModerationRequest, ModerationResponse, ModerationResult
from trussium.observability.propagation import outbound_trace_context_headers
from trussium.providers.openai.chat import OpenAIChatCapability


class OpenAIModerationCapability:
    provider_name = "openai"

    def __init__(self, client: AsyncOpenAI) -> None:
        self._client = client

    async def moderate(self, request: ModerationRequest) -> ModerationResponse:
        try:
            response = await self._client.moderations.create(
                model=request.model,
                input=request.input,
                extra_headers=outbound_trace_context_headers(),
            )
        except APIError as error:
            raise OpenAIChatCapability._normalize_api_error(error) from error
        results = [
            ModerationResult(
                flagged=result.flagged,
                categories=result.categories.model_dump(),
                category_scores=result.category_scores.model_dump(),
            )
            for result in response.results
        ]
        return ModerationResponse(
            id=response.id, provider=self.provider_name, model=request.model, results=results
        )
