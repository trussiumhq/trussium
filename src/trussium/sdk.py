"""Typed Python client for an existing Trussium runtime."""

from typing import Any

import httpx

from trussium.capabilities.batches.models import BatchCreateRequest, BatchJob
from trussium.capabilities.chat.models import ChatCompletionRequest, ChatCompletionResponse
from trussium.capabilities.embeddings.models import EmbeddingsRequest, EmbeddingsResponse
from trussium.capabilities.images.models import ImageGenerationRequest, ImageGenerationResponse
from trussium.capabilities.moderation.models import ModerationRequest, ModerationResponse
from trussium.capabilities.reranking.models import RerankingRequest, RerankingResponse
from trussium.capabilities.transcription.models import TranscriptionRequest, TranscriptionResponse


class TrussiumClientError(RuntimeError):
    """Raised when a Trussium runtime request cannot complete."""


class TrussiumClient:
    """Synchronous typed client for a configured Trussium runtime URL."""

    def __init__(
        self, base_url: str = "http://127.0.0.1:9000", *, timeout_seconds: float = 30.0
    ) -> None:
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout_seconds)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "TrussiumClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        return ChatCompletionResponse.model_validate(
            self._request("POST", "/v1/chat/completions", request.model_dump())
        )

    def embeddings(self, request: EmbeddingsRequest) -> EmbeddingsResponse:
        return EmbeddingsResponse.model_validate(
            self._request("POST", "/v1/embeddings", request.model_dump())
        )

    def moderations(self, request: ModerationRequest) -> ModerationResponse:
        return ModerationResponse.model_validate(
            self._request("POST", "/v1/moderations", request.model_dump())
        )

    def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        return ImageGenerationResponse.model_validate(
            self._request("POST", "/v1/images/generations", request.model_dump())
        )

    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResponse:
        data = {"model": request.model}
        for name in ("language", "prompt", "temperature"):
            value = getattr(request, name)
            if value is not None:
                data[name] = str(value)
        try:
            response = self._client.post(
                "/v1/audio/transcriptions",
                data=data,
                files={
                    "file": (
                        request.audio.filename,
                        request.audio.data,
                        request.audio.content_type or "application/octet-stream",
                    )
                },
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise TrussiumClientError("The Trussium runtime returned an invalid response.")
            return TranscriptionResponse.model_validate(payload)
        except httpx.HTTPError as error:
            raise TrussiumClientError("The Trussium runtime request failed.") from error

    def rerank(self, request: RerankingRequest) -> RerankingResponse:
        return RerankingResponse.model_validate(
            self._request("POST", "/v1/rerankings", request.model_dump())
        )

    def create_batch(self, request: BatchCreateRequest) -> BatchJob:
        return BatchJob.model_validate(self._request("POST", "/v1/batches", request.model_dump()))

    def get_batch(self, batch_id: str) -> BatchJob:
        return BatchJob.model_validate(self._request("GET", f"/v1/batches/{batch_id}"))

    def cancel_batch(self, batch_id: str) -> BatchJob:
        return BatchJob.model_validate(self._request("POST", f"/v1/batches/{batch_id}/cancel"))

    def readiness(self) -> dict[str, Any]:
        return self._request("GET", "/health/ready")

    def capabilities(self) -> dict[str, Any]:
        return self._request("GET", "/v1/capabilities/availability")

    def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            response = self._client.request(method, path, json=payload)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise TrussiumClientError("The Trussium runtime returned an invalid response.")
            return payload
        except httpx.HTTPError as error:
            raise TrussiumClientError("The Trussium runtime request failed.") from error
