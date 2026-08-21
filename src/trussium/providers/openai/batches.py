"""OpenAI Batch API adapter."""

from openai import APIError, AsyncOpenAI
from openai.types.batch import Batch

from trussium.capabilities.batches import BatchCreateRequest, BatchJob
from trussium.observability.propagation import outbound_trace_context_headers
from trussium.providers.openai.chat import OpenAIChatCapability


class OpenAIBatchCapability:
    provider_name = "openai"

    def __init__(self, client: AsyncOpenAI) -> None:
        self._client = client

    async def create(self, request: BatchCreateRequest) -> BatchJob:
        try:
            batch = await self._client.batches.create(
                completion_window="24h",
                endpoint=request.endpoint,
                input_file_id=request.input_file_id,
                extra_headers=outbound_trace_context_headers(),
            )
        except APIError as error:
            raise OpenAIChatCapability._normalize_api_error(error) from error
        return self._normalize(batch)

    async def retrieve(self, batch_id: str) -> BatchJob:
        try:
            batch = await self._client.batches.retrieve(
                batch_id, extra_headers=outbound_trace_context_headers()
            )
        except APIError as error:
            raise OpenAIChatCapability._normalize_api_error(error) from error
        return self._normalize(batch)

    async def cancel(self, batch_id: str) -> BatchJob:
        try:
            batch = await self._client.batches.cancel(
                batch_id, extra_headers=outbound_trace_context_headers()
            )
        except APIError as error:
            raise OpenAIChatCapability._normalize_api_error(error) from error
        return self._normalize(batch)

    def _normalize(self, batch: Batch) -> BatchJob:
        return BatchJob(
            id=batch.id,
            provider=self.provider_name,
            status=batch.status,
            endpoint=batch.endpoint,
            input_file_id=batch.input_file_id,
            output_file_id=batch.output_file_id,
            error_file_id=batch.error_file_id,
        )
