# OpenTelemetry Tracing Guide

Trussium can export vendor-neutral request and execution traces through OTLP
over HTTP/protobuf. Tracing is disabled by default, so a runtime without trace
configuration creates no exporter and performs no collector network requests.

## Trace contract

One sampled chat request produces this hierarchy:

```text
HTTP POST                         SERVER
└── trussium.capability.chat      INTERNAL
    └── trussium.provider.chat    CLIENT
```

The server span covers the complete HTTP response, including the final body of
an SSE stream. Capability and provider spans likewise remain active until their
ordinary or streaming execution completes, fails, or is cancelled.

`/health/live`, `/health/ready`, and `/metrics` are excluded. Probes and
scrapes therefore do not create trace traffic.

## Configuration

Enable tracing and point Trussium at the HTTP/protobuf traces endpoint exposed
by an OpenTelemetry Collector or compatible backend:

```bash
export TRUSSIUM_OBSERVABILITY__TRACING_ENABLED=true
export TRUSSIUM_OBSERVABILITY__TRACING_SERVICE_NAME=trussium
export TRUSSIUM_OBSERVABILITY__TRACING_SAMPLE_RATIO=1.0
export TRUSSIUM_OBSERVABILITY__OTLP_TRACES_ENDPOINT=http://127.0.0.1:4318/v1/traces
export TRUSSIUM_OBSERVABILITY__OTLP_EXPORT_TIMEOUT_SECONDS=10
uv run python -m trussium
```

| Setting | Default | Contract |
|---|---:|---|
| `TRUSSIUM_OBSERVABILITY__TRACING_ENABLED` | `false` | Construct the SDK provider and exporter. |
| `TRUSSIUM_OBSERVABILITY__TRACING_SERVICE_NAME` | `trussium` | Non-empty OpenTelemetry `service.name`. |
| `TRUSSIUM_OBSERVABILITY__TRACING_SAMPLE_RATIO` | `1.0` | Root sampling probability from `0.0` through `1.0`; remote parent decisions are honored. |
| `TRUSSIUM_OBSERVABILITY__OTLP_TRACES_ENDPOINT` | `http://127.0.0.1:4318/v1/traces` | Full HTTP or HTTPS OTLP traces URL. |
| `TRUSSIUM_OBSERVABILITY__OTLP_EXPORT_TIMEOUT_SECONDS` | `10` | Positive export request deadline. |

Configuration is typed, validated at startup, and immutable afterward. For a
production deployment, start with a sampling ratio appropriate to traffic
volume and collector capacity. A ratio of `0` suppresses new root samples but
still honors a sampled inbound parent through parent-based sampling.

## Context and structured logs

Trussium extracts the W3C `traceparent` header on inbound workload requests.
A valid remote parent therefore anchors the runtime server span in the caller's
trace. Invalid or absent context safely starts a new root according to the
configured sampler.

Every structured lifecycle log emitted inside an active sampled span
automatically includes:

- `trace_id`: lowercase, zero-padded 32-character hexadecimal trace ID.
- `span_id`: lowercase, zero-padded 16-character hexadecimal span ID.

Existing `request_id`, `execution_id`, capability, provider, and model fields
remain unchanged. The shared trace ID joins HTTP, capability, and provider
events; their span IDs identify the active layer.

## Attributes and privacy

The runtime records bounded operational attributes:

- HTTP method, matched route template, and response status.
- Request and execution IDs.
- Capability and provider names.
- Requested model and streaming mode.
- Completed, failed, or cancelled outcome.
- Bounded error code or exception type and cancellation reason.
- OpenTelemetry GenAI operation, provider, and requested-model attributes.

Trussium does not attach prompts, completions, request or response bodies,
query strings, credentials, headers, raw URLs, or exception messages. Health
and scrape exclusions plus route templates prevent unbounded HTTP path data.
Apply access control and retention policy in the collector and backend because
request IDs, model names, and provider names are still operational metadata.

## Lifecycle and export behavior

Each FastAPI application owns its own tracer provider, resource, sampler, span
processor, and exporter. Trussium does not replace the process-global
OpenTelemetry provider. This avoids provider conflicts in embedded and test
processes and makes multiple application instances deterministic.

The production exporter uses the OpenTelemetry batch span processor. Pending
spans are flushed and its worker is shut down during the application lifespan
shutdown. Set the orchestrator termination grace period long enough for normal
request draining and exporter shutdown.

## Collector deployment

Trussium does not install or configure an OpenTelemetry Collector. In Docker,
Kubernetes, and other isolated networks, the loopback default points back to
the runtime container or pod. Set the endpoint to a reachable collector
Service, for example:

```text
http://otel-collector.observability.svc:4318/v1/traces
```

The checked-in Kubernetes base keeps tracing disabled. A deployment-owned
overlay or Helm values should enable it only after supplying a reachable
endpoint and an intentional sampling policy.

## Current boundary

This feature extracts inbound W3C context and traces the runtime's internal
HTTP, capability, and provider layers. It does not yet inject `traceparent`
into the outbound provider HTTP request. That cross-service propagation,
provider HTTP transport instrumentation, and end-to-end collector validation
are the next distributed-tracing roadmap item.

## Troubleshooting

- Confirm the endpoint is the full OTLP HTTP traces URL, normally ending in
  `/v1/traces`, rather than the OTLP gRPC port.
- Confirm the runtime network can reach the collector and that the collector
  accepts `application/x-protobuf` on the configured endpoint.
- Check sampling configuration and any inbound parent's sampled flag when no
  spans appear.
- Allow the batch processor time to export, or stop the runtime cleanly so
  pending spans are flushed.
- Use correlated structured logs to obtain a trace ID without enabling payload
  capture.
