# API usage examples

These examples call a self-hosted Trussium runtime. Start it locally with
`trussium serve`; its default address is `http://127.0.0.1:9000`. Replace that
address with a private service URL when running in your own network.

## Health and capability discovery

```bash
curl http://127.0.0.1:9000/health/ready
curl http://127.0.0.1:9000/v1/capabilities/availability
```

## Chat completion over HTTP

```bash
curl http://127.0.0.1:9000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gpt-4.1-mini",
    "messages": [{"role": "user", "content": "Hello from Trussium"}]
  }'
```

The configured provider must support the requested model. Do not place provider
credentials in requests; configure them in the runtime environment instead.

## Python SDK

```python
from trussium.capabilities.chat.models import ChatCompletionRequest, ChatMessage, ChatRole
from trussium.sdk import TrussiumClient

request = ChatCompletionRequest(
    model="gpt-4.1-mini",
    messages=[ChatMessage(role=ChatRole.USER, content="Hello from Trussium")],
)

with TrussiumClient("http://127.0.0.1:9000") as client:
    print(client.readiness())
    print(client.capabilities())
    completion = client.complete(request)
```
