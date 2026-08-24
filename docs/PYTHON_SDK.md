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
