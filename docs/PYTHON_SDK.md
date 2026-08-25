# Python SDK

The Python SDK is maintained in the dedicated
[`trussium-python`](https://github.com/trussiumhq/trussium-python) repository and
published as the `trussium-sdk` package. It calls an existing local, private,
or public runtime; it does not install, host, or configure one.

```bash
pip install trussium-sdk
```

```python
from trussium_sdk import TrussiumClient

with TrussiumClient("http://127.0.0.1:9000") as client:
    response = client.complete(
        {"model": "gpt-4.1-mini", "messages": [{"role": "user", "content": "Hello"}]},
        request_id="request-123",
    )
```

The package supports chat, embeddings, moderation, image generation,
transcription, reranking, batch jobs, video jobs, controlled tools, readiness,
and capability discovery. Audio bytes are sent only to the configured runtime;
tool authority remains owned by the runtime's allowlist.
