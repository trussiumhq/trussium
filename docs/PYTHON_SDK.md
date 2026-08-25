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
