# Production API reference

Trussium exposes a versioned, provider-neutral HTTP API on port `9000` by
default. Use the generated OpenAPI document at `/openapi.json` and interactive
`/docs` only on trusted networks; the stable contract is the `/v1` path.

## Endpoint groups

| Group | Endpoints | Purpose |
| --- | --- | --- |
| Health | `GET /health/live`, `GET /health/ready`, `GET /health/components` | Process liveness, traffic readiness, and informational component state. |
| Capabilities | `GET /v1/capabilities`, `/availability`, `/health` | Discover configured capability contracts and informational state. |
| Providers | `GET /v1/providers`, `/v1/providers/health`, `/v1/providers/{name}/models` | Discover providers, health, and optional model metadata. |
| Chat | `POST /v1/chat/completions` | Normalized JSON or Server-Sent Events chat execution. |
| AI capabilities | `POST /v1/embeddings`, `/v1/moderations`, `/v1/images/generations`, `/v1/rerankings`, `/v1/translations` | Provider-neutral non-streaming operations. |
| Audio/video | `POST /v1/audio/speech`, `/v1/audio/transcriptions`, `/v1/videos`; `GET /v1/videos/{id}` | Speech, transcription, and video-job contracts. |
| Batch/tools | `POST /v1/batches`, `GET/POST /v1/batches/{id}[/cancel]`, `POST /v1/tools/executions` | Application-owned batch and controlled tool execution. |

## Production requirements

- Wait for `GET /health/ready`; use `/health/live` only for restart decisions.
- Send non-sensitive caller correlation through `X-Request-ID`; preserve it on
  responses and logs. It is not an authentication or idempotency token.
- Treat the JSON `detail.code` and safe `detail.message` as the stable error
  contract. Validation failures use `validation_error` and bounded field paths.
- For chat SSE, consume through the terminal event, close on cancellation, and
  apply an application-owned outer deadline.
- Keep credentials in runtime-managed secrets. Never place them in requests,
  IDs, logs, traces, metrics labels, or discovery responses.
- Pin `/v1`; additive changes are compatible, while breaking changes require a
  separately documented major API path.

See [API Usage](API_USAGE.md) for copyable requests, [Integration](INTEGRATION.md)
for SDK/client guidance, and [Self-Hosted Operations](SELF_HOSTING.md) for
deployment, probes, scaling, and rollback.
