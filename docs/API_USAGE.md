# API usage examples

For the complete production endpoint and operational contract, see the
[Production API Reference](API_REFERENCE.md).

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

## Provider examples

Trussium keeps provider adapters behind one normalized API. Use the built-in
OpenAI-compatible boundary for OpenAI or a compatible endpoint such as vLLM:

```bash
export TRUSSIUM_PROVIDER__NAME=openai
export TRUSSIUM_PROVIDER__BASE_URL=https://api.openai.com/v1
export TRUSSIUM_PROVIDER__API_KEY=replace-with-a-secret
```

For a private vLLM deployment, point the same boundary at its reachable URL:

```bash
export TRUSSIUM_PROVIDER__NAME=openai
export TRUSSIUM_PROVIDER__BASE_URL=http://vllm.internal:8000/v1
export TRUSSIUM_PROVIDER__API_KEY=replace-with-a-secret
```

For Ollama, use its OpenAI-compatible endpoint:

```bash
export TRUSSIUM_PROVIDER__NAME=ollama
export TRUSSIUM_PROVIDER__BASE_URL=http://127.0.0.1:11434/v1
```

The standalone [`trussium-provider-anthropic`](https://github.com/trussiumhq/trussium-provider-anthropic)
adapter translates Anthropic Messages into the normalized chat contract. It
must be installed and explicitly registered by the embedding application; it
does not install or host Anthropic.

## Python SDK

```python
from trussium_sdk import TrussiumClient

with TrussiumClient("http://127.0.0.1:9000") as client:
    print(client.readiness())
    print(client.capabilities())
    completion = client.complete(
        {
            "model": "gpt-4.1-mini",
            "messages": [{"role": "user", "content": "Hello from Trussium"}],
        }
    )
```

Install with `pip install trussium-sdk`; the independent package calls the
runtime and does not install or host it.

## Translation

```bash
curl http://127.0.0.1:9000/v1/translations \
  -H 'Content-Type: application/json' \
  -H 'X-Request-ID: translation-123' \
  -d '{"model":"translator","input":["Hello world"],"source_language":"en","target_language":"fr"}'
```

The runtime must have a registered translation provider, such as the
self-hosted [LibreTranslate adapter](https://github.com/trussiumhq/trussium-provider-libretranslate).

## Troubleshooting responses

Check the response status before debugging provider details:

| Status | First action |
| --- | --- |
| `200` | Inspect the normalized response or stream events. |
| `400` / `422` | Validate the request shape, required fields, and model name. |
| `404` | Confirm the endpoint path and capability is enabled. |
| `503` | Check provider configuration, credentials, network reachability, and readiness. |
| `504` | Review runtime provider or stream-idle deadlines and upstream latency. |

Collect the `X-Request-ID` response header and matching structured logs for
correlation. Do not include credentials, prompts, provider payloads, or raw
exception text in tickets.
