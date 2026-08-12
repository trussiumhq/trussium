# Runtime Health and Dependency Readiness

Trussium separates process health from external dependency availability:

- `GET /health/live` proves that the runtime process and HTTP event loop are
  serving requests. It never calls a provider and should be used for container
  restart decisions.
- `GET /health/ready` proves that the runtime can receive traffic. By default
  it preserves the original local-only response. Operators may explicitly
  enable provider and optional model dependency gating.

Do not use an external provider outage to fail liveness. Restarting a healthy
runtime cannot restore a provider network, credential, permission, quota, or
model dependency and may amplify an incident.

## Default behavior

Dependency checks are disabled by default. Both endpoints return HTTP 200:

```json
{"status":"ok"}
```

The default makes no provider request and preserves deployments that start
without provider credentials. The chat endpoint continues to return its
existing `chat_capability_unavailable` service error when no provider is
configured.

## Enable dependency-aware readiness

Configure the runtime before startup:

```text
TRUSSIUM_READINESS__DEPENDENCY_CHECKS_ENABLED=true
TRUSSIUM_READINESS__DEPENDENCY_TIMEOUT_SECONDS=1
TRUSSIUM_READINESS__DEPENDENCY_CACHE_SECONDS=10
TRUSSIUM_READINESS__REQUIRED_MODEL=gpt-5-mini
```

| Setting | Default | Contract |
| --- | --- | --- |
| `TRUSSIUM_READINESS__DEPENDENCY_CHECKS_ENABLED` | `false` | Gate readiness on provider metadata access. |
| `TRUSSIUM_READINESS__DEPENDENCY_TIMEOUT_SECONDS` | `1` | Strictly positive runtime-owned deadline for one refresh. |
| `TRUSSIUM_READINESS__DEPENDENCY_CACHE_SECONDS` | `10` | Strictly positive monotonic result lifetime. |
| `TRUSSIUM_READINESS__REQUIRED_MODEL` | unset | Optional non-blank model that must be retrievable by the configured credential. |

With no required model, Trussium lists provider model metadata. This proves
that the compatible API is reachable and accepts the configured credential.
With a required model, Trussium retrieves that model's metadata. Neither mode
sends a prompt, requests inference, consumes completion tokens, or evaluates
model quality, quota sufficiency, latency SLOs, or future request success.

OpenAI and Ollama use the same provider-neutral dependency result over their
compatible model metadata APIs.

## Responses

A healthy required provider returns HTTP 200:

```json
{
  "status": "ok",
  "dependencies": [
    {
      "name": "provider",
      "status": "ok",
      "provider": "openai",
      "model": "gpt-5-mini"
    }
  ]
}
```

An unavailable dependency returns HTTP 503:

```json
{
  "status": "unavailable",
  "dependencies": [
    {
      "name": "provider",
      "status": "unavailable",
      "provider": "openai",
      "model": "gpt-5-mini",
      "reason": "provider_authentication_failed"
    }
  ]
}
```

Stable failure reasons are:

| Reason | Meaning |
| --- | --- |
| `provider_not_configured` | Dependency gating is enabled but the selected provider cannot be constructed. |
| `provider_authentication_failed` | The provider rejected the configured credential. |
| `provider_permission_denied` | The credential is authenticated but cannot access metadata. |
| `provider_rate_limited` | The provider rejected the metadata request because of throttling. |
| `provider_timeout` | The SDK or runtime-owned deadline expired. |
| `provider_unreachable` | The provider could not be reached. |
| `model_unavailable` | The configured required model metadata was not found. |
| `provider_check_failed` | The provider returned another bounded or unexpected failure. |

These codes are operational classifications, not routing decisions. They do
not trigger retry, fallback, circuit breaking, provider replacement, or model
aliasing.

## Timeout, cache, and concurrency

The runtime deadline is independent of provider SDK defaults. A probe that
exceeds it returns `provider_timeout`; caller cancellation still propagates.

Successful and failed results share the configured monotonic cache lifetime.
This bounds provider traffic and makes outage behavior deterministic. Once a
result expires, the first readiness request refreshes it. Concurrent requests
wait on that single refresh rather than fanning out provider calls. A fresh
failure replaces a success and a fresh success replaces a failure.

Use Kubernetes `failureThreshold` and `successThreshold` for rollout
hysteresis. Application caching is not a substitute for platform probe
thresholds.

## Kubernetes rollout guidance

The maintained Kustomize and Helm defaults leave dependency checks disabled.
Before enabling them:

1. Confirm pod egress, DNS, proxy, firewall, and service-mesh policy.
2. Confirm the provider Secret is present before the rollout.
3. Confirm the credential can access model metadata.
4. Set a required model only when one model must gate all pod traffic.
5. Keep the dependency timeout below the Kubernetes readiness probe timeout.
6. Tune the cache and probe thresholds to avoid provider request amplification.
7. Use a staged rollout and verify both 200 and intentional 503 responses.

If a provider Secret is optional and may be absent, leave dependency checks
disabled. Enabling them deliberately changes missing provider configuration
from locally ready to HTTP 503.

## Observability

Health endpoints remain excluded from Trussium workload metrics and runtime
traces. Dependency checks do not emit capability or provider execution
lifecycles because they are metadata probes, not user executions.

Startup emits `readiness.configuration.loaded` with only enablement, timeout,
cache, and required-model-present fields. A refreshed dependency logs only a
state transition:

- `readiness.dependency.ok`
- `readiness.dependency.unavailable`

Repeated cached states do not produce repeated events. Failure events use the
same stable reason in `error_code`. The health-check SDK client is closed during
application shutdown; cleanup failure is reported as
`readiness.dependency.shutdown.failed`.

## Privacy and security

Readiness bodies and operational events never include credentials, provider
or proxy endpoints, headers, payloads, provider response bodies, exception
messages, or tracebacks. The configured provider and optional required model
are operational identifiers already used by the runtime contract. Treat model
names as deployment metadata and omit `REQUIRED_MODEL` if disclosing one is
not acceptable.

Do not expose health endpoints directly to untrusted public networks. Apply
normal ingress, NetworkPolicy, authentication-boundary, and log-access controls
at the platform layer.

## Troubleshooting

- `provider_not_configured`: verify the selected provider and Secret injection.
- `provider_authentication_failed`: rotate or correct the credential without
  logging it.
- `provider_permission_denied`: grant metadata/model access to the credential.
- `provider_rate_limited`: increase the cache, reduce probe frequency, and
  review provider limits.
- `provider_timeout` or `provider_unreachable`: verify DNS, egress, proxy,
  service mesh, firewall, and provider availability.
- `model_unavailable`: verify the exact provider model identifier and account
  access, or remove the required-model gate.
- `provider_check_failed`: inspect bounded operational events and provider-side
  telemetry without copying raw responses into Trussium logs.

During an external outage, do not change liveness or restart healthy pods.
Choose whether to keep dependency gating, temporarily disable it, or stop
traffic according to the deployment's availability and degradation policy.
