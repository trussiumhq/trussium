# Runtime Alerting and Runbook Guide

Trussium provides a portable Prometheus starter-rule profile for the runtime's
stable metric contract. It is a reviewed operational baseline, not a universal
service-level objective or paging policy.

The rules are maintained at
`deploy/observability/prometheus/rules/trussium-runtime-alerts.yaml` and
validated with Prometheus 3.6.0. They require no Trussium-specific loader and
do not install Prometheus, Alertmanager, Grafana Alerting, notification routes,
or Kubernetes custom resources.

## Reference profile

| Alert | Severity | Reference condition | Hold |
|---|---|---|---|
| `TrussiumRuntimeTelemetryMissing` | warning | No `trussium_http_requests_active` series is visible | 15 minutes |
| `TrussiumRuntimeRequestFailuresHigh` | critical | Failures exceed 5% while traffic exceeds 0.1 requests/second | 10 minutes |
| `TrussiumRuntimeRequestCancellationsHigh` | warning | Cancellations exceed 10% while traffic exceeds 0.1 requests/second | 15 minutes |
| `TrussiumRuntimeRequestLatencyHigh` | warning | P95 duration exceeds 5 seconds while traffic exceeds 0.1 requests/second | 10 minutes |
| `TrussiumRuntimeProcessRestarted` | warning | A target's process start time changed within 15 minutes | 5 minutes |

Failure and cancellation ratios are separate. A failed execution generally
represents runtime or upstream service impact. A cancellation can be normal
client behavior, an intermediary timeout, a disconnect, shutdown enforcement,
or capacity pressure and should not inherit critical severity automatically.

Minimum-traffic guards prevent idle and very-low-volume instances from firing
ratio or latency alerts on statistically weak samples. They also mean this
profile is not sufficient for a low-volume critical service; such a deployment
may need synthetic requests or different objectives.

## Adopt and validate

For a standalone Prometheus server, copy the rule file to an operator-owned
location and reference it from `rule_files`:

```yaml
rule_files:
  - /etc/prometheus/rules/trussium-runtime-alerts.yaml
```

Reload Prometheus using the deployment's supported configuration lifecycle.
Do not add credentials or notification destinations to the rule file.

Prometheus Operator users can copy the `groups` array into an
organization-owned `PrometheusRule` after reviewing labels, selectors,
thresholds, and routing. Trussium does not ship or apply that custom resource
because its availability, namespace, tenancy, and admission policy are
cluster-specific.

Validate tracked syntax and synthetic behavior locally:

```bash
scripts/alert-rules-smoke-test.sh
```

The script runs digest-pinned `promtool check rules` and `promtool test rules`
inside a network-isolated, read-only container. Synthetic scenarios prove each
alert fires under its reference condition and that low traffic does not
activate ratio alerts.

## Tune before paging

Review the following for every deployment:

- Measured request rate, failure ratio, cancellation ratio, and latency
  percentiles across representative busy and quiet periods.
- User-facing objectives and the duration of impact that warrants a page,
  ticket, or dashboard-only warning.
- Replica topology and stability of Prometheus `job` and `instance` labels.
- Planned deploy, restart, scaling, and maintenance behavior.
- Provider and intermediary timeout policies, especially for streaming work.
- Sampling, retention, and access policy in Loki and Tempo when those optional
  diagnostic backends are used.

Change thresholds and `for` durations in deployment-owned copies. Preserve
alert names only when their meaning remains compatible; otherwise use an
organization-specific name so runbooks and routing do not misrepresent the
condition.

The missing-telemetry rule detects absence of all Trussium active-request
series visible to that Prometheus evaluation context. It is not a per-instance
availability rule. Use the deployment's target-health or `up` alerts for
individual scrape targets and route those through platform runbooks.

The process-restart rule assumes stable `job` and `instance` labels across a
restart. Kubernetes pod identity often changes on replacement, so platform
restart counters and workload status remain complementary signals.

## Routing and lifecycle

The included `severity` values express the reference profile only:

- `critical` indicates sustained request failure at meaningful traffic.
- `warning` indicates investigation is appropriate before user impact is
  assumed.

Alertmanager grouping should normally include alert name, environment, cluster,
namespace, job, and service ownership where those labels are added by the
deployment. Avoid grouping or routing on request, execution, trace, model, or
provider identifiers.

Recommended deployment policy:

- Route warnings to a staffed operational queue unless measured objectives
  justify paging.
- Page on critical failures only after defining an owner, acknowledgement
  target, escalation path, and maintenance behavior.
- Inhibit latency and ratio symptoms when a confirmed broader platform or
  scrape outage already explains them.
- Silence alerts through an audited maintenance process rather than editing
  tracked rule files during a deployment.
- Require a resolved notification and recovery evidence before closing an
  incident.

## Common triage workflow

1. Confirm the alert labels, start time, current value, and whether the
   condition is still firing.
2. Open `Trussium Runtime Overview` with the same time range, `job`, and
   `instance` where available.
3. Compare request demand, active work, outcomes, p95/p99 latency, process CPU,
   resident memory, and uptime.
4. Use `Trussium Runtime Logs` or the platform log search for bounded lifecycle
   and operational events.
5. If Tempo is available, inspect failed or slow traces and confirm whether
   impact is in the HTTP, capability, provider, or downstream-owned span.
6. Check deployment rollout, replica, resource, network, collector, and
   provider status using their owning systems.
7. Apply the least disruptive mitigation, then confirm metrics recover for at
   least the alert's range and hold windows.
8. Record the cause, mitigation, recovery evidence, and any threshold or
   runbook change separately from the incident timeline.

Loki and Tempo are diagnostic aids, not dependencies for evaluating these
Prometheus rules.

## TrussiumRuntimeTelemetryMissing

Meaning: Prometheus has seen no Trussium active-request series for 15 minutes.
This can indicate scrape discovery, network, authentication, relabeling,
metrics disablement, or complete runtime absence.

Triage:

- Check Prometheus targets and scrape errors before assuming runtime failure.
- Confirm `/metrics` is enabled and reachable at port 9000 through the intended
  network and authentication boundary.
- Verify the query's Prometheus tenant and time range.
- Check runtime pod/process status and recent rollout activity.
- Confirm dashboards select the same Prometheus data source.

Mitigation depends on ownership: restore scrape discovery or credentials,
repair the network path, re-enable intentionally required metrics, or restore
runtime replicas. Do not restart healthy workloads solely because telemetry is
missing.

Resolution evidence: the active-request series is present continuously beyond
the alert hold period and target-health alerts are resolved.

## TrussiumRuntimeRequestFailuresHigh

Meaning: a `job` and `instance` sustained more than 5% failed workload requests
at meaningful traffic for 10 minutes.

Triage:

- Compare outcome and HTTP status panels to identify normalized failure shape.
- Search request, capability, and provider `.failed` lifecycle events.
- Inspect stable error codes and exception class names without relying on
  exception text or payload capture.
- Use failed traces to locate the affected execution layer when Tempo exists.
- Check provider quotas, authentication, reachability, and status in the
  provider-owned control plane.
- Check runtime resource pressure and rollout changes.

Mitigation may include rolling back a deployment, restoring a dependency,
correcting operator-owned credentials, reducing traffic, or invoking a tested
provider contingency. Never copy credentials or prompts into incident alerts.

Resolution evidence: failure ratio remains below the deployment objective for
at least the five-minute query range plus ten-minute hold, with representative
traffic and successful end-to-end requests.

## TrussiumRuntimeRequestCancellationsHigh

Meaning: cancellations exceeded 10% at meaningful traffic for 15 minutes.
Cancellation is not automatically a runtime defect.

Triage:

- Separate client disconnects, runtime shutdown cancellation, upstream timeout,
  and streaming idle timeout using bounded lifecycle fields.
- Compare active work and latency with cancellation timing.
- Check load balancer, ingress, client, provider-request, stream-idle, and
  graceful-shutdown timeouts for incompatible deadlines.
- Inspect rollout and termination events for drain timeouts.
- Sample affected traces only when privacy and retention policy permit.

Mitigation may require aligning timeout budgets, restoring capacity, pausing a
rollout, or correcting a client/intermediary. Treat deliberate user
cancellation as expected demand and tune the threshold rather than suppressing
unrelated failures.

Resolution evidence: cancellation ratio returns to the deployment baseline
through the full range and hold period and the identified lifecycle cause is
no longer present.

## TrussiumRuntimeRequestLatencyHigh

Meaning: p95 end-to-end request duration exceeded five seconds at meaningful
traffic for 10 minutes. Streaming duration includes the complete response body
and may require a workload-specific objective.

Triage:

- Compare p50, p95, and p99 to distinguish broad slowdown from a tail issue.
- Segment dashboard queries by bounded method and outcome where helpful.
- Inspect active work, CPU, memory, replicas, and autoscaler status.
- Use slow traces to distinguish HTTP, capability, provider, and downstream
  latency when Tempo exists.
- Compare provider and network status with runtime timing.

Mitigation may include restoring capacity, addressing a provider or network
incident, rolling back a regression, or temporarily reducing demand. Do not
reduce sampling or disable telemetry as a latency mitigation without evidence
that telemetry itself is causal.

Resolution evidence: p95 stays below the deployment objective with meaningful
traffic for the query range and hold period.

## TrussiumRuntimeProcessRestarted

Meaning: Prometheus observed a changed process start time for a stable target.
One restart can be planned; repeated or correlated restarts require
investigation.

Triage:

- Check rollout history, desired state, termination reason, exit code, and
  container platform events.
- Review runtime configuration, startup, stopping, stopped, and shutdown events.
- Look for resource eviction, liveness failure, node disruption, or operator
  action in the platform.
- Confirm whether the target label survived the restart; absence of this alert
  does not prove no pod replacement occurred.

Mitigation follows the owning cause: roll back invalid configuration, restore
resources, correct probe or termination timing, or repair platform instability.

Resolution evidence: desired replicas remain ready, restarts stop, health and
workload metrics remain stable, and startup/shutdown logs show expected
outcomes.

## Operational-event escalation guide

These structured events are useful diagnostic or ticket signals but are not
shipped as executable Loki alerts because ruler, tenancy, label, and routing
contracts vary by deployment.

| Event | Suggested handling |
|---|---|
| `runtime.configuration.invalid` | Investigate immediately; the process exits with bounded validation evidence. |
| `provider.configuration.unavailable` | Act only when provider capability is expected; this reports local configuration, not provider reachability. |
| `runtime.shutdown.drain_timeout` | Investigate workload duration, client behavior, and termination timing. |
| `runtime.shutdown.cleanup_timeout` | Review cancellation cleanup and resource release; warning severity is normally appropriate. |
| `observability.trace_export.failed` | Restore trace export when tracing is required; runtime requests may remain healthy. |
| `observability.tracing.shutdown.failed` | Review exporter shutdown and termination timing. |
| `runtime.stopped` with failed outcome | Correlate application cleanup failures with platform restart behavior. |
| `runtime.shutdown.completed` with failed outcome | Review server drain and cleanup evidence before declaring graceful termination. |

Prefer rate or duration windows over one-event paging unless the event proves
immediate user impact. Never promote provider configuration readiness to a
network, credential, quota, or model-health assertion.

## Privacy and cardinality

The starter rules use only bounded runtime and process metrics plus Prometheus
target identity. They do not use paths, requests, executions, tenants,
providers, models, traces, or spans as metric labels.

Alert notifications should not contain prompts, completions, bodies,
credentials, arbitrary headers, raw URLs, provider or collector endpoints, raw
settings, rejected configuration values, exception messages, or stack traces.
Correlation identifiers may be used in access-controlled investigation tools
after an alert fires, subject to retention policy; they should not become
metric labels or default notification payloads.

## Ownership boundary

Trussium owns the stable starter-rule and runbook contract. Operators own
scraping, rule loading, SLOs, threshold changes, Alertmanager or Grafana
configuration, notification receivers, credentials, schedules, escalation,
silences, access control, retention, and incident management.

The runtime image, Python distributions, Kustomize resources, and official Helm
chart install no alerts or observability backends. Readiness dependency checks
remain a separate roadmap item.
