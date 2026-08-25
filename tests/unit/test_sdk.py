import httpx
import pytest

from trussium.capabilities.batches.models import BatchCreateRequest
from trussium.capabilities.embeddings.models import EmbeddingsRequest
from trussium.capabilities.images.models import ImageGenerationRequest
from trussium.capabilities.moderation.models import ModerationRequest
from trussium.capabilities.reranking.models import RerankingDocument, RerankingRequest
from trussium.capabilities.transcription.models import AudioInput, TranscriptionRequest
from trussium.sdk import TrussiumClient, TrussiumClientError


def test_readiness_uses_configured_runtime_url() -> None:
    client = TrussiumClient("http://runtime")
    client._client = httpx.Client(
        base_url="http://runtime",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"status": "ok"})),
    )
    assert client.readiness() == {"status": "ok"}
    client.close()


def test_transport_errors_are_normalized() -> None:
    client = TrussiumClient("http://runtime")
    client._client = httpx.Client(
        base_url="http://runtime",
        transport=httpx.MockTransport(
            lambda _: (_ for _ in ()).throw(httpx.ConnectError("unavailable"))
        ),
    )
    with pytest.raises(TrussiumClientError):
        client.capabilities()
    client.close()


def test_embeddings_and_moderations_use_typed_contracts() -> None:
    responses = iter(
        (
            {
                "id": "embedding-1",
                "provider": "stub",
                "model": "embed",
                "data": [{"index": 0, "embedding": [0.1]}],
                "usage": {"input_tokens": 1, "total_tokens": 1},
            },
            {
                "id": "moderation-1",
                "provider": "stub",
                "model": "moderate",
                "results": [{"flagged": False, "categories": {}, "category_scores": {}}],
            },
        )
    )
    client = TrussiumClient("http://runtime")
    client._client = httpx.Client(
        base_url="http://runtime",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=next(responses))),
    )

    assert client.embeddings(EmbeddingsRequest(model="embed", input=["hello"])).data[0].index == 0
    assert (
        client.moderations(ModerationRequest(model="moderate", input=["hello"])).results[0].flagged
        is False
    )
    client.close()


def test_images_and_transcription_use_typed_contracts() -> None:
    responses = iter(
        (
            {
                "id": "image-1",
                "provider": "stub",
                "model": "image",
                "data": [{"b64_json": "aW1hZ2U="}],
            },
            {"id": "audio-1", "provider": "stub", "model": "audio", "text": "hello"},
        )
    )
    client = TrussiumClient("http://runtime")
    client._client = httpx.Client(
        base_url="http://runtime",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=next(responses))),
    )
    assert (
        client.generate_image(ImageGenerationRequest(model="image", prompt="tree")).id == "image-1"
    )
    assert (
        client.transcribe(
            TranscriptionRequest(
                model="audio", audio=AudioInput(filename="audio.wav", data=b"audio")
            )
        ).text
        == "hello"
    )
    client.close()


def test_reranking_and_batch_lifecycle_use_typed_contracts() -> None:
    responses = iter(
        (
            {
                "id": "rank-1",
                "provider": "stub",
                "model": "rank",
                "results": [{"index": 0, "relevance_score": 1.0}],
            },
            {
                "id": "batch-1",
                "provider": "stub",
                "status": "validating",
                "endpoint": "/v1/chat/completions",
                "input_file_id": "file-in",
            },
            {
                "id": "batch-1",
                "provider": "stub",
                "status": "completed",
                "endpoint": "/v1/chat/completions",
                "input_file_id": "file-in",
                "output_file_id": "file-out",
            },
            {
                "id": "batch-1",
                "provider": "stub",
                "status": "cancelling",
                "endpoint": "/v1/chat/completions",
                "input_file_id": "file-in",
            },
        )
    )
    client = TrussiumClient("http://runtime")
    client._client = httpx.Client(
        base_url="http://runtime",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=next(responses))),
    )
    assert (
        client.rerank(
            RerankingRequest(model="rank", query="q", documents=[RerankingDocument(text="d")])
        )
        .results[0]
        .index
        == 0
    )
    assert client.create_batch(BatchCreateRequest(input_file_id="file-in")).status == "validating"
    assert client.get_batch("batch-1").output_file_id == "file-out"
    assert client.cancel_batch("batch-1").status == "cancelling"
    client.close()
