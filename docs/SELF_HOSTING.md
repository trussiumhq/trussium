# Self-Hosted Operations Guide

Trussium can run on a laptop, private network, or Kubernetes cluster without a
Trussium-hosted control plane. The runtime listens on port `9000`; callers use
that address directly, including through the Python SDK. Choose the deployment
boundary, network policy, secret store, log collection, metrics backend, and
trace collector that fit your environment.

This guide coordinates the runtime's operational contracts. It does not replace
the detailed [Container Guide](CONTAINERS.md), [Kubernetes Deployment
Guide](KUBERNETES.md), [Runtime Health and Dependency Readiness
Guide](HEALTH.md), [Runtime Metrics Guide](METRICS.md), [Structured Operational
Logging Guide](OPERATIONAL_LOGGING.md), or [OpenTelemetry Tracing
Guide](TRACING.md).

## Start a private runtime

For a local development or private-host deployment, install the locked project
dependencies, configure a provider, validate the typed settings, and start the
runtime:

```bash
uv sync --all-groups
export TRUSSIUM_PROVIDER__NAME=ollama
export TRUSSIUM_PROVIDER__BASE_URL=http://127.0.0.1:11434/v1
trussium config validate
trussium serve
```

The default listener is `http://127.0.0.1:9000`. In a private environment,
place the runtime behind your normal internal load balancer, ingress, or
service-discovery boundary. Do not publish provider credentials to callers:
inject them through the operating system, container platform, or secret store.
For OpenAI-compatible configuration and private Ollama endpoints, see
[DEVELOPMENT.md](DEVELOPMENT.md).

`trussium config validate` exits with status `2` when settings are invalid.
`trussium health --url http://127.0.0.1:9000` checks readiness and exits with
status `1` if the runtime is unavailable. The [CLI Guide](CLI.md) documents the
complete command boundary.

## Deploy containers and Kubernetes

Use the production image when the runtime is owned by a container platform:

```bash
docker run --rm --publish 9000:9000 ghcr.io/trussiumhq/trussium:<version>
```

Use your platform's secret injection instead of placing credentials in a shell
command. The [Container Guide](CONTAINERS.md) covers hardened options, provider
environment files, image validation, shutdown, and a reachable Ollama address.

For a copyable single-host deployment, start from the maintained
[`templates/self-hosted-runtime`](../templates/self-hosted-runtime) Compose
starter:

```bash
cd templates/self-hosted-runtime
docker compose config
docker compose up -d
curl http://127.0.0.1:9000/health/ready
```

Review the template's provider settings and replace its example values before
using it outside a local or private development environment. Compose starts the
Trussium runtime; it does not install the separate `trussium-operator` project.

For Kubernetes, the maintained Kustomize production overlay creates the
runtime workload, Service, health probes, metrics endpoint, and optional
provider Secret integration. The independently versioned official Helm chart
packages that same runtime contract. It installs `trussium` runtime resources
only; it does not install the separate Trussium Operator. See the [Kubernetes
Deployment Guide](KUBERNETES.md) for private registry access, Secret keys,
customization, upgrades, rollback, scaling, and removal.

The `trussium-operator` project is separately versioned and responsible for
Kubernetes reconciliation. Its installation and custom-resource lifecycle are
outside this runtime repository and this guide.

## Health and traffic decisions

Probe the runtime according to the endpoint's purpose:

| Endpoint | Use |
| --- | --- |
| `GET /health/live` | Restart decision: proves the process and HTTP event loop are serving. |
| `GET /health/ready` | Traffic decision: proves the runtime can receive work. |
| `GET /health/components` | Informational component state; it never gates traffic. |
| `GET /v1/capabilities/availability` | Informational capability availability; it never gates execution. |

Provider dependency checks are disabled by default. Enable them only after
provider credentials, DNS, egress, proxy, and the required model are known to
be available. Keep liveness independent of a provider outage: restarting a
healthy runtime cannot repair a remote credential, quota, or network failure.
The [Health Guide](HEALTH.md) defines the settings, response codes, stable
failure reasons, and rollout guidance.

## Observe the runtime

Scrape `GET /metrics` with an existing Prometheus-compatible system. The
endpoint is enabled by default and intentionally excludes health and scrape
traffic from workload metrics. Do not add request IDs, execution IDs, provider
names, or model names as metric labels; they remain bounded correlation fields
in logs and traces. See the [Metrics Guide](METRICS.md), [Dashboards
Guide](DASHBOARDS.md), and [Alerting Guide](ALERTING.md).

Collect standard output as newline-delimited JSON. Request-scoped operational
events automatically inherit request, execution, capability, provider, model,
trace, and span identifiers when they are available. Preserve those fields as
structured attributes and do not collect credentials, payloads, or exception
messages. The [Structured Operational Logging Guide](OPERATIONAL_LOGGING.md)
defines the stable event and privacy contracts.

Tracing is disabled by default. Enable it only after providing a collector that
is reachable from the runtime's network and choosing an intentional sampling
ratio. The [Tracing Guide](TRACING.md) documents OTLP configuration, context
propagation, exporter shutdown, and privacy limits.

## Upgrade and rollback

Treat a runtime upgrade as a deployment change:

1. Select an immutable released package or container version.
2. Validate the intended runtime configuration with `trussium config validate`.
3. Roll out through your normal deployment mechanism and wait for
   `/health/ready` before sending traffic.
4. Verify metrics, structured startup events, and—if enabled—traces.
5. Retain the prior known-good version and configuration reference.

If the rollout is unhealthy, stop or reverse traffic using your platform, then
redeploy the prior version. Do not change liveness to mask a provider outage.
The Kubernetes and Helm upgrade/rollback procedures are authoritative in the
[Kubernetes Deployment Guide](KUBERNETES.md); the [Container
Guide](CONTAINERS.md) is authoritative for image tags and container behavior.

## Troubleshooting

| Symptom | First action |
| --- | --- |
| Runtime will not start | Run `trussium config validate`; correct the reported configuration category without exposing secret values. |
| Readiness returns `503` | Inspect the stable reason in the [Health Guide](HEALTH.md); verify Secret injection, DNS, egress, proxy, credential access, and required-model availability. |
| Liveness is healthy but inference fails | Keep the runtime running and investigate the provider configuration or capability response; liveness deliberately does not test providers. |
| No metrics or traces | Confirm `/metrics` is reachable, metrics are enabled, and any OTLP collector address is reachable from the runtime network. |
| Missing execution correlation | Collect JSON logs intact and preserve request, execution, capability, provider, model, trace, and span fields as attributes rather than metric labels. |
| Pods do not become ready during rollout | Check `/health/ready`, provider dependency-gate configuration, and Kubernetes probe timing before increasing restart pressure. |

For incident response, use bounded Trussium events and platform/provider
telemetry. Never paste credentials, request bodies, provider responses, or raw
exception messages into operational logs or tickets.
