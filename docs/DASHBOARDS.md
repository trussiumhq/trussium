# Runtime Dashboards Guide

Trussium provides three independently importable Grafana dashboards for the
runtime's stable metrics, structured logs, and distributed traces. The JSON
models are version controlled in
`deploy/observability/grafana/dashboards/` and validated against Grafana
12.2.0.

| Dashboard | UID | Backend | Purpose |
|---|---|---|---|
| Trussium Runtime Overview | `trussium-runtime-overview` | Prometheus | Request demand, active work, success, failures, latency, status, CPU, memory, and uptime. |
| Trussium Runtime Logs | `trussium-runtime-logs` | Loki | Runtime lifecycle, provider configuration, execution failures, shutdown outcomes, and the structured event stream. |
| Trussium Runtime Traces | `trussium-runtime-traces` | Tempo | Recent, failed, and slow traces plus HTTP, capability, and provider span searches. |

Prometheus is required for the overview. Loki and Tempo are optional; import
only the dashboards supported by the deployment's observability stack.
Trussium does not install Grafana, Prometheus, Loki, Tempo, an OpenTelemetry
Collector, log agents, or operator custom resources.

## Import

Each tracked file is a Grafana dashboard model and can be uploaded directly
through **Dashboards → New → Import**. Select the matching data source when
Grafana prompts for it.

For API-based import, wrap the model in Grafana's request envelope:

```bash
jq -n \
  --slurpfile dashboard deploy/observability/grafana/dashboards/trussium-runtime-overview.json \
  '{dashboard: $dashboard[0], overwrite: true}' \
  > /tmp/trussium-dashboard-import.json

curl --fail-with-body \
  --header "Authorization: Bearer ${GRAFANA_SERVICE_ACCOUNT_TOKEN}" \
  --header "Content-Type: application/json" \
  --data-binary @/tmp/trussium-dashboard-import.json \
  "${GRAFANA_URL}/api/dashboards/db"
```

Use the same command with either remaining JSON file. The stable UID makes an
import with `overwrite: true` an intentional update of that dashboard.

Grafana file provisioning can instead mount the three JSON files into a
dashboard provider directory. A minimal provider resembles:

```yaml
apiVersion: 1
providers:
  - name: Trussium
    folder: Trussium
    type: file
    disableDeletion: true
    updateIntervalSeconds: 30
    options:
      path: /var/lib/grafana/dashboards
```

The repository smoke fixture under `tests/fixtures/grafana/provisioning/`
shows a complete test-only example. Its loopback data-source URLs are not
production defaults and do not appear in the dashboard artifacts.

## Data collection contract

### Prometheus

Scrape each Trussium instance on port 9000 at `/metrics`. The overview uses
only the documented request and process instruments. Its `job` and `instance`
variables filter every query, including p50, p95, and p99 request duration.
Health and scrape requests remain excluded from the workload series.

### Loki

Collect container standard output and preserve each Trussium JSON object as a
single log line. The deployment's log pipeline must add bounded `job` and
`instance` stream labels. Dashboard queries parse `event`, `level`, `logger`,
and correlation metadata from JSON at query time; they do not require those
fields to become Loki index labels.

### Tempo

Enable Trussium OTLP trace export to a collector that writes to Tempo. The
dashboard's `service` variable defaults to `trussium` and should match
`TRUSSIUM_OBSERVABILITY__TRACING_SERVICE_NAME`. Its TraceQL searches preserve
the runtime hierarchy:

```text
HTTP POST
└── trussium.capability.chat
    └── trussium.provider.chat
```

The `slow_threshold` variable accepts a TraceQL duration such as `1s` or
`500ms`.

## Operator workflow

Start with the overview to identify demand, latency, active streams, process
pressure, or failed and cancelled work. Pivot to structured logs for stable
events and correlation identifiers. Use a correlated `trace_id`, or the Tempo
failed and slow searches, to inspect the complete execution hierarchy.

The dashboards intentionally define no alerts. Portable Prometheus starter
rules and matching runbooks are maintained separately so threshold review,
evaluation, routing, and notification ownership remain explicit. See the
[Runtime Alerting and Runbook Guide](ALERTING.md).

## Privacy and cardinality

Dashboard queries do not add telemetry or widen the runtime's collection
boundary. Metrics remain limited to bounded method, outcome, and status-code
dimensions; request, execution, provider, model, and trace identifiers are not
metric labels. Loki parses correlation fields at query time. Trace searches use
the bounded attributes already emitted by Trussium.

No dashboard contains credentials, backend URLs, provider endpoints, prompts,
completions, request or response bodies, arbitrary headers, or exception
messages. Operators remain responsible for access control and retention in
Grafana and each selected backend.

## Validation and troubleshooting

Run the static query-contract tests and the pinned real-Grafana import test:

```bash
uv run pytest tests/unit/observability/test_dashboards.py
scripts/dashboard-smoke-test.sh
```

If a dashboard has no data:

- Confirm the selected data source can query its backend from Grafana.
- Confirm Prometheus is scraping `/metrics` and select the matching `job` and
  `instance` values.
- Confirm Loki stream labels include `job` and `instance` and JSON parsing
  exposes the documented `event` field.
- Confirm tracing is enabled, the collector exports to Tempo, and `service`
  matches the configured OpenTelemetry service name.
- Expand the time range and, for traces, relax `slow_threshold`.

No-data panels do not imply that runtime health checks or provider readiness
have failed; verify those contracts independently.
