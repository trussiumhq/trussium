# Structured Operational Logging Guide

Trussium emits newline-delimited JSON operational events to standard output.
These events complement request, capability, and provider execution lifecycles
with process-level configuration, startup, shutdown, and telemetry state.

## Event contract

Every event contains `timestamp`, `level`, `logger`, `message`, and `event`.
Additional fields are selected from a fixed allowlist so operational logs stay
bounded and machine-readable.

| Event | Level | Meaning |
|---|---|---|
| `runtime.configuration.invalid` | ERROR | Typed startup settings were rejected; the process exits with status 2. |
| `runtime.configuration.loaded` | INFO | Safe runtime settings were accepted. |
| `provider.configuration.ready` | INFO | A provider capability was constructed from configuration. |
| `provider.configuration.unavailable` | WARNING | No provider capability was constructed; health endpoints remain available. |
| `readiness.configuration.loaded` | INFO | Bounded dependency-readiness settings were loaded. |
| `readiness.dependency.ok` | INFO | A refreshed required dependency became available. |
| `readiness.dependency.unavailable` | WARNING | A refreshed required dependency became unavailable with a stable reason code. |
| `readiness.dependency.shutdown.failed` | ERROR | The readiness metadata client could not close cleanly. |
| `observability.configuration.loaded` | INFO | Metrics and tracing settings were accepted. |
| `runtime.started` | INFO | The application lifespan is ready. |
| `runtime.shutdown.started` | INFO | The server stopped accepting new work and began draining. |
| `runtime.shutdown.drain_timeout` | ERROR | Active work exceeded the configured graceful-shutdown deadline. |
| `runtime.shutdown.cleanup_timeout` | WARNING | Cancelled work exceeded the bounded cleanup period. |
| `runtime.stopping` | INFO | Application lifespan shutdown began. |
| `observability.trace_export.failed` | ERROR | The OTLP exporter returned or raised a failure. |
| `observability.tracing.shutdown.completed` | INFO | App-scoped tracing shutdown completed or tracing was disabled. |
| `observability.tracing.shutdown.failed` | ERROR | App-scoped tracing shutdown raised an exception. |
| `runtime.stopped` | INFO or ERROR | Application lifespan shutdown completed, with an `outcome`. |
| `runtime.shutdown.completed` | INFO or ERROR | Server shutdown completed, with an `outcome` and duration. |

Provider configuration events report local configuration readiness. They do
not prove dependency availability by themselves. When dependency checks are
explicitly enabled, separate readiness events and `/health/ready` use bounded
provider metadata checks. See [HEALTH.md](HEALTH.md).

## Example

With no provider credential and tracing disabled, startup includes records
like these, one JSON object per line:

```json
{"level":"INFO","logger":"trussium.runtime","message":"Runtime configuration loaded","event":"runtime.configuration.loaded","runtime_version":"0.30.0","environment":"production","port":9000,"debug":false,"graceful_shutdown_seconds":30}
{"level":"WARNING","logger":"trussium.provider","message":"Provider configuration unavailable","event":"provider.configuration.unavailable","provider":"openai","provider_configured":false}
{"level":"INFO","logger":"trussium.readiness","message":"Readiness configuration loaded","event":"readiness.configuration.loaded","dependency_checks_enabled":false,"dependency_timeout_seconds":1.0,"dependency_cache_seconds":10.0,"required_model_configured":false}
{"level":"INFO","logger":"trussium.observability","message":"Observability configuration loaded","event":"observability.configuration.loaded","metrics_enabled":true,"tracing_enabled":false,"trace_sample_ratio":1.0}
{"level":"INFO","logger":"trussium.runtime","message":"Runtime started","event":"runtime.started"}
```

Production records also contain an ISO 8601 UTC `timestamp`. Field order is not
an API contract; event names, field meanings, and JSON value types are.

## Bounded fields

Configuration summaries may include:

- Runtime version, environment, port, debug mode, and drain deadline.
- Provider name and a boolean configuration-ready state.
- Metrics and tracing enablement plus the trace sampling ratio.

Shutdown events may include active or unfinished task counts, configured
deadlines, duration, and a bounded outcome. Trace-export failures may include a
span count and exception class name, but not exception text.

Request-scoped logs continue to inherit request, execution, capability,
provider, model, trace, and span identifiers from the active runtime context.
Process-level events normally have no request or execution context.

## Privacy boundary

Trussium operational events do not serialize:

- Provider credentials or authorization headers.
- Provider or collector URLs.
- Raw environment variables, settings objects, or rejected input values.
- Prompts, completions, request bodies, response bodies, or span payloads.
- Exception messages, stack traces, or exporter response bodies.
- Arbitrary task names or objects.

Invalid configuration produces one bounded structured event and exits with
status 2 without printing Pydantic's rejected values. Third-party library and
platform logs are outside the Trussium event schema and should be governed by
the deployment's normal collection and retention policy.

## Collection and dashboards

Collect standard output with the container platform's existing log pipeline
and parse each JSON line. Preserve `event`, `level`, and correlation fields as
structured attributes. Alerting and dashboard definitions are not installed by
the runtime. The versioned `Trussium Runtime Logs` dashboard provides Loki
queries for configuration, lifecycle, execution, shutdown, and export events
without turning correlation fields into index labels. See the
[Runtime Dashboards Guide](DASHBOARDS.md) for collection expectations, import,
and privacy boundaries. The
[Runtime Alerting and Runbook Guide](ALERTING.md) maps high-value operational
events to investigation and escalation guidance without shipping a
backend-specific Loki ruler configuration.
