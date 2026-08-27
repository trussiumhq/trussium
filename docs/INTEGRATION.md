# Application Integration Guide

Applications integrate with Trussium over its stable HTTP runtime boundary.
The runtime can run on a laptop, private host, container, or Kubernetes
service. SDKs are convenience clients for that same boundary; they do not
install, host, or configure the runtime.

## 1. Start and verify the runtime

Use the [Self-Hosted Operations Guide](SELF_HOSTING.md) or the
[Project Templates Guide](PROJECT_TEMPLATES.md) to choose a deployment. For a
local source checkout:

```bash
uv sync --all-groups
trussium config validate
trussium serve
```

The default address is `http://127.0.0.1:9000`. Wait for traffic readiness
before sending application work:

```bash
trussium health --url http://127.0.0.1:9000
trussium capabilities --url http://127.0.0.1:9000
```

`/health/live` is a process/liveness signal. `/health/ready` is the traffic
decision. Capability discovery and availability are informational and do not
replace readiness or authorize requests.

## 2. Choose an integration surface

The repository includes a runnable [Python client application example](../examples/python-app/README.md)
that uses the dedicated SDK against an already running Trussium runtime. It
demonstrates readiness, capability discovery, request-ID forwarding, chat, and
translation without hosting providers or embedding credentials.

All clients call the same JSON and SSE contracts:

| Surface | When to use | Guide |
| --- | --- | --- |
| REST | language-neutral services, scripts, and gateways | [API Usage](API_USAGE.md) |
| Python | Python applications | [Python SDK](PYTHON_SDK.md) |
| Go | Go services and CLIs | [Go SDK](GO_SDK.md) |
| TypeScript | Node.js and TypeScript applications | [TypeScript SDK](TYPESCRIPT_SDK.md) |

The Python and Go packages are published independently. TypeScript semantic
release creates tags and GitHub releases while npm publication remains
deferred; source builds are documented in the TypeScript guide.

## 3. Make a first request

REST clients can call the normalized completion endpoint directly:

```bash
curl http://127.0.0.1:9000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H 'X-Request-ID: checkout-demo-001' \
  -d '{
    "model": "llama3.1:8b",
    "messages": [{"role": "user", "content": "Say hello."}],
    "stream": false
  }'
```

The configured provider must support the requested model. Provider credentials
belong in the runtime environment or secret store, never in application
requests. See the [Provider Development Guide](PROVIDER_DEVELOPMENT.md) when
adding or selecting a provider adapter.

## 4. Correlate requests and executions

Send a stable caller-owned `X-Request-ID` when the application already has a
request or job identity. Trussium preserves it in successful and error
responses and propagates it through asynchronous, streaming, provider, and
structured-log lifecycles. When omitted, the runtime generates a bounded UUID.

Request IDs are correlation values, not authentication, authorization, or
idempotency keys. Do not put credentials, prompts, tenant secrets, or payloads
in them. Preserve JSON logs intact so operators can pivot across
`request_id`, `execution_id`, `capability`, `provider`, `model`, `trace_id`, and
`span_id` where available. See [Operational Logging](OPERATIONAL_LOGGING.md)
and [Tracing](TRACING.md).

## 5. Handle responses, errors, and streams

Treat non-2xx responses as runtime failures and inspect the bounded `error.code`
and safe message. Do not depend on provider SDK exception types at the
application boundary; SDKs expose their own typed API errors while REST
preserves the normalized JSON envelope. See [Errors](ERRORS.md).

Streaming requests use Server-Sent Events. Consume until the terminal event,
close the response on cancellation or client disconnect, and do not assume a
provider-specific event schema:

```bash
curl -N http://127.0.0.1:9000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H 'X-Request-ID: checkout-stream-001' \
  -d '{"model":"llama3.1:8b","messages":[{"role":"user","content":"Stream hello."}],"stream":true}'
```

The runtime owns provider request deadlines, stream-idle deadlines, upstream
cleanup, and cancellation lifecycle. Applications should set their own outer
request deadline and propagate cancellation without retrying a partially
consumed stream.

## 6. Discover capabilities safely

Use `GET /v1/capabilities` to discover the public, provider-neutral operations
configured in the runtime. Use `GET /v1/capabilities/availability` for bounded
informational availability. Neither endpoint exposes provider credentials,
implementations, model inventories, or private endpoints.

Capability execution remains owned by the runtime. Applications should select a
documented capability and send its normalized request rather than infer provider
selection or call provider APIs directly. The [Capability Development Guide](CAPABILITY_DEVELOPMENT.md)
documents the extension boundary.

## 7. Operate privately

Keep the runtime on a private network or behind an authenticated internal
gateway. Inject provider credentials through the deployment platform, rotate
them outside application payloads, and restrict egress to required providers.
Enable metrics, logs, and tracing deliberately while preserving their privacy
contracts. The runtime does not provide a hosted control plane and the SDKs do
not install the separate `trussium-operator` or Helm chart.

For production rollout, probes, scaling, secrets, and rollback, follow the
[Container Guide](CONTAINERS.md) or [Kubernetes Guide](KUBERNETES.md). For
provider and capability extensions, use the dedicated development guides.

The [complete Python example application](../examples/python-app/README.md)
demonstrates these steps as a small FastAPI service with `/health`,
`/capabilities`, and `/ask` endpoints.

## Integration checklist

- [ ] Runtime configuration validates before startup.
- [ ] Application waits for `/health/ready`.
- [ ] Application uses REST or an SDK against the runtime URL.
- [ ] Request IDs are stable, non-sensitive correlation values.
- [ ] Errors use bounded codes and safe messages.
- [ ] Streaming responses are closed on cancellation or disconnect.
- [ ] Provider credentials remain in runtime-managed secrets.
- [ ] Logs, metrics, traces, and deployment probes follow their guides.
