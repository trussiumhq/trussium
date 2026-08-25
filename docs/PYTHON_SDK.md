# Python SDK

The Python SDK calls an existing Trussium runtime; it does not install or host one.

```python
from trussium.sdk import TrussiumClient

with TrussiumClient("http://127.0.0.1:9000") as client:
    readiness = client.readiness()
```

The initial client also supports typed embeddings and moderation requests:

```python
from trussium.capabilities.embeddings.models import EmbeddingsRequest
from trussium.capabilities.moderation.models import ModerationRequest

with TrussiumClient("http://127.0.0.1:9000") as client:
    embeddings = client.embeddings(EmbeddingsRequest(model="text-embedding-3-small", input=["hello"]))
    moderation = client.moderations(ModerationRequest(model="omni-moderation-latest", input=["hello"]))
```

Image generation and transcription use their existing typed contracts. Audio
bytes are sent only to the configured runtime and are not stored by the SDK.

```python
from trussium.capabilities.images.models import ImageGenerationRequest
from trussium.capabilities.transcription.models import AudioInput, TranscriptionRequest

with TrussiumClient("http://127.0.0.1:9000") as client:
    image = client.generate_image(ImageGenerationRequest(model="gpt-image-1", prompt="a tree"))
    audio = client.transcribe(TranscriptionRequest(model="whisper-1", audio=AudioInput(filename="audio.wav", data=b"...")))
```

Reranking and batch-job metadata are also supported. Batch input and output
files remain provider-owned; the SDK accepts only the existing input-file ID.

```python
from trussium.capabilities.batches.models import BatchCreateRequest
from trussium.capabilities.reranking.models import RerankingDocument, RerankingRequest

with TrussiumClient("http://127.0.0.1:9000") as client:
    ranking = client.rerank(RerankingRequest(model="rerank", query="hello", documents=[RerankingDocument(text="hello world")]))
    batch = client.create_batch(BatchCreateRequest(input_file_id="file-provider-owned"))
    current = client.get_batch(batch.id)
```

Video jobs return metadata only. Tool invocation can call only a runtime
application's pre-registered allowlisted tools; the SDK cannot register or
broaden tool authority.

```python
from trussium.capabilities.videos.models import VideoCreateRequest
from trussium.tools.contracts import ToolInvocation

with TrussiumClient("http://127.0.0.1:9000") as client:
    video = client.create_video(VideoCreateRequest(model="sora-2", prompt="a tree"))
    current_video = client.get_video(video.id)
    result = client.execute_tool(ToolInvocation(name="echo", arguments={"value": "hello"}))
```
