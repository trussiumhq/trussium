"""Hugging Face Text Embeddings Inference reranking adapter."""

from uuid import uuid4

import httpx

from trussium.capabilities.errors import CapabilityErrorCategory, CapabilityExecutionError
from trussium.capabilities.reranking import (
    RerankingRequest,
    RerankingResponse,
    RerankingResult,
)
from trussium.observability.propagation import outbound_trace_context_headers


class TEIRerankingCapability:
    provider_name = "tei"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def rerank(self, request: RerankingRequest) -> RerankingResponse:
        try:
            response = await self._client.post(
                "/rerank",
                json={
                    "query": request.query,
                    "texts": [document.text for document in request.documents],
                    "raw_scores": False,
                    **({"top_n": request.top_n} if request.top_n is not None else {}),
                },
                headers=outbound_trace_context_headers(),
            )
            response.raise_for_status()
        except httpx.TimeoutException as error:
            raise CapabilityExecutionError(
                code="reranking_provider_timeout",
                message="The reranking provider timed out.",
                category=CapabilityErrorCategory.UPSTREAM_TIMEOUT,
            ) from error
        except httpx.RequestError as error:
            raise CapabilityExecutionError(
                code="reranking_provider_connection_failed",
                message="The reranking provider could not be reached.",
                category=CapabilityErrorCategory.UPSTREAM_CONNECTION,
            ) from error
        except httpx.HTTPStatusError as error:
            category = (
                CapabilityErrorCategory.INVALID_REQUEST
                if error.response.status_code == 400
                else CapabilityErrorCategory.UPSTREAM_FAILURE
            )
            raise CapabilityExecutionError(
                code="reranking_provider_failed",
                message="The reranking provider rejected the request.",
                category=category,
            ) from error
        try:
            payload = response.json()
            results = [
                RerankingResult(index=item["index"], relevance_score=item["score"])
                for item in payload
            ]
        except (KeyError, TypeError, ValueError) as error:
            raise CapabilityExecutionError(
                code="reranking_provider_invalid_response",
                message="The reranking provider returned an invalid response.",
                category=CapabilityErrorCategory.UPSTREAM_FAILURE,
            ) from error
        if not results:
            raise CapabilityExecutionError(
                code="reranking_provider_invalid_response",
                message="The reranking provider returned an invalid response.",
                category=CapabilityErrorCategory.UPSTREAM_FAILURE,
            )
        return RerankingResponse(
            id=str(uuid4()), provider=self.provider_name, model=request.model, results=results
        )
