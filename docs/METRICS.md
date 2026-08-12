# Runtime Metrics Guide

Trussium exposes Prometheus-compatible runtime metrics at `GET /metrics` by
default. Each application instance owns an isolated registry containing Python,
process, and Trussium HTTP instruments.

## Metric contract

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `trussium_http_requests_active` | Gauge | None | Workload requests currently executing, including active SSE streams. |
| `trussium_http_requests_total` | Counter | `method`, `outcome`, `status_code` | Terminal workload request results. |
| `trussium_http_request_duration_seconds` | Histogram | `method`, `outcome` | Full request duration through the terminal response body. |

`outcome` is one of `completed`, `failed`, or `cancelled`. A request that fails
before starting a response is recorded with status `500`; a cancelled request
without a response status uses `499`.

The health and metrics endpoints are excluded from workload instruments:

- `/health/live`
- `/health/ready`
- `/metrics`

This keeps probes and scrapes from distorting request demand. Labels are
deliberately bounded. Paths, request IDs, execution IDs, tenants, providers,
and model names are not metric labels.

The standard Python client also exposes Python runtime metrics on every
platform and process metrics on supported Linux environments.

## Configuration

Metrics are enabled by default. Disable the endpoint and instrumentation with:

```bash
export TRUSSIUM_OBSERVABILITY__METRICS_ENABLED=false
```

Start Trussium and inspect the registry:

```bash
uv run python -m trussium
curl http://127.0.0.1:9000/metrics
```

The endpoint uses the official Prometheus client exposition content type and
is intentionally omitted from the public OpenAPI document.

## Prometheus scraping

The runtime does not install Prometheus. Configure an existing Prometheus,
Prometheus Operator `ServiceMonitor`, or compatible collector to scrape port
`9000` at `/metrics`. Apply authentication and network policy at the platform
boundary when the endpoint must not be generally reachable.

The active-request gauge can later be exported through Prometheus Adapter as a
custom autoscaling metric. The maintained Kubernetes production overlay does
not require that optional integration: its default HorizontalPodAutoscaler
uses the standard per-container CPU resource metric from Kubernetes Metrics
API.

## Grafana overview

The versioned `Trussium Runtime Overview` dashboard queries this exact metric
contract for demand, active work, success percentage, failures and
cancellations, p50/p95/p99 duration, status distribution, process CPU, resident
memory, and uptime. Select its Prometheus data source plus the deployment's
`job` and `instance` values after import. The dashboard does not introduce new
labels, recording rules, scrape configuration, or alerts. See the
[Runtime Dashboards Guide](DASHBOARDS.md) for import and provisioning.

## Alerting profile

The portable Prometheus starter rules use this exact bounded contract for
missing telemetry, sustained failures, sustained cancellations, high p95
duration, and process restarts. Ratio and latency conditions include a
minimum-traffic guard. The reference thresholds are not universal SLOs and the
runtime installs no rule engine or notification route. See the
[Runtime Alerting and Runbook Guide](ALERTING.md).

## Streaming semantics

Instrumentation wraps the pure ASGI request lifecycle. An SSE request remains
active until its terminal body is sent, the client disconnects, execution is
cancelled, or an exception escapes. This makes the gauge useful for capacity
analysis of long-running streams without adding stream- or request-specific
labels.
