# Trussium example application

This small FastAPI service demonstrates an application integrating with an
existing, self-hosted Trussium runtime through the independent `trussium-sdk`
package. It does not install, host, or configure Trussium.

## Run it

Start a provider-free or configured runtime first, then run the application:

```bash
cp .env.example .env
uv sync
uv run uvicorn app:app --reload --port 8000
```

The application reads `TRUSSIUM_URL` and `TRUSSIUM_MODEL`; the defaults target
the runtime at `http://127.0.0.1:9000` and model `llama3.1:8b`.

## Try the endpoints

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/capabilities
curl http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -H 'X-Request-ID: example-demo-001' \
  -d '{"prompt":"Say hello in one sentence."}'
```

`/health` and `/capabilities` call the runtime's readiness and public discovery
endpoints. `/ask` forwards the caller's `X-Request-ID`, or creates an
application-owned correlation ID when the header is absent. Provider credentials
remain in the runtime environment, never in this application request.

Stop the application with `Ctrl-C`. Stop the runtime through its own CLI or
deployment mechanism. For production concerns, see the [Integration Guide](../../docs/INTEGRATION.md)
and [Self-Hosted Operations Guide](../../docs/SELF_HOSTING.md).
