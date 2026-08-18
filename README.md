# Trussium

> **The cloud-native runtime for AI applications.**

Build AI applications once. Run them anywhere.

[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![Status](https://img.shields.io/badge/status-early--development-orange)
![gRPC](https://img.shields.io/badge/gRPC-first-4285F4)
![Cloud Native](https://img.shields.io/badge/cloud--native-kubernetes-326CE5)

---

## What is Trussium?

Trussium is a cloud-native AI application runtime that provides a consistent interface for AI models, agents, tools, and protocols across any provider and deployment environment.

Instead of integrating directly with provider-specific SDKs, applications integrate once with Trussium.

```text
                    Applications
                          │
           REST      gRPC      MCP
                \      │      /
                 \     │     /
                 Trussium Runtime
                        │
               Provider Framework
                        │
   OpenAI • Anthropic • Gemini • Ollama • Bedrock • ...
```

The runtime abstracts provider differences while providing production-grade capabilities such as routing, streaming, observability, extensibility, and governance.

---

## Why Trussium?

Modern AI infrastructure is becoming increasingly fragmented.

- Every provider exposes different APIs.
- Applications become tightly coupled to provider-specific SDKs.
- Supporting multiple providers significantly increases complexity.
- Emerging protocols, tools, and agents introduce new integration challenges.

Trussium provides a unified runtime that allows applications to remain independent of individual providers.

### Core Principles

- **Provider Agnostic** — Integrate once and switch providers without changing application code.
- **Protocol Agnostic** — Support REST, gRPC, MCP, and future protocols.
- **Cloud Native** — Designed for Kubernetes and modern infrastructure from day one.
- **Extensible** — Providers, protocols, routing strategies, and plugins are fully extensible.
- **Observable** — Structured logging, metrics, and tracing are built into the platform.
- **Production Ready** — Built for reliability, scalability, and enterprise deployments.

---

## Architecture

```text
                    Applications
                          │
          REST       gRPC        MCP
             \         │         /
              \        │        /
               Trussium Runtime
                      │
              Runtime Services
                      │
             Provider Framework
                      │
 ┌──────────────┬──────────────┬──────────────┐
 │              │              │              │
OpenAI      Anthropic      Gemini       Ollama
```

The runtime is intentionally independent of individual AI providers.

---

## Project Status

🚧 **Early Development**

Trussium is currently in active development.

The architecture is being built in public, and breaking changes are expected until the first stable release.

---

## Quick Start

```bash
git clone https://github.com/trussiumhq/trussium-runtime.git

cd trussium-runtime

uv venv

source .venv/bin/activate

uv sync --extra dev --extra docs
```

Start the runtime locally:

```bash
uv run python -m trussium
```

Trussium listens on port 9000 by default. Health endpoints remain available
without provider credentials. Prometheus-compatible runtime metrics are
available at `http://127.0.0.1:9000/metrics`. App-scoped OpenTelemetry tracing
and OTLP/HTTP export are available through explicit observability settings.
Enabled traces continue across OpenAI and Ollama-compatible provider requests
through privacy-bounded W3C Trace Context propagation. Tracing remains disabled
by default. Startup, configuration, shutdown, graceful-drain, and trace-export
state is emitted as bounded structured operational JSON without credentials,
payloads, endpoints, or exception messages.
Portable Grafana dashboards turn those stable Prometheus, Loki, and Tempo
contracts into operator views without installing or configuring observability
backends.
Portable Prometheus starter rules and matching runbooks add explicit reference
conditions for missing telemetry, failures, cancellations, latency, and process
restarts while leaving SLOs, routing, and notification ownership to operators.
Provider dependency readiness is opt-in and can gate `/health/ready` on
bounded OpenAI or Ollama-compatible metadata access and an optional required
model. Liveness remains local and provider-independent. See the
[Runtime Health and Dependency Readiness Guide](docs/HEALTH.md).

Trussium-owned failures share a public typed exception hierarchy with stable
machine-readable codes and client-safe messages. Existing capability and
provider errors remain compatible, while cancellation, validation, framework,
and unnormalized SDK exceptions keep their native semantics. See the
[Runtime Exception Hierarchy Guide](docs/ERRORS.md).

Application-scoped runtime services can use a typed asynchronous lifecycle
contract with ordered startup, reverse shutdown, partial-startup rollback, and
bounded cleanup. See the
[Runtime Service Lifecycle Guide](docs/LIFECYCLE.md).

A public application-scoped registry adds explicit ordered registration,
stable optional and required lookup, immutable discovery snapshots, duplicate
protection, and lifecycle-backed ownership. See the
[Runtime Service Registry Guide](docs/SERVICE_REGISTRY.md).

Registered services can optionally report bounded component health through an
informational ordered aggregate that remains independent of liveness and
readiness. See the
[Runtime Component Health Reporting Guide](docs/COMPONENT_HEALTH.md).

Provider-neutral capabilities now use a sealed insertion-ordered registry for
explicit registration, stable lookup, immutable discovery, duplicate
protection, and application-owned execution composition. The existing chat
factory shortcut remains compatible. See the
[Core Capability Registry Guide](docs/CAPABILITY_REGISTRY.md).

Configured capability contracts now carry bounded immutable metadata and are
externally discoverable in registration order through `GET /v1/capabilities`.
Discovery exposes no provider, model, implementation, health, availability, or
configuration data. See the
[Capability Metadata and Discovery Guide](docs/CAPABILITY_DISCOVERY.md).

A sealed-registry-backed execution pipeline now provides one provider-neutral
boundary for asynchronous and streaming capability work. It resolves canonical
identities once, preserves execution context and native error semantics, and
closes upstream streams without changing the existing chat JSON, SSE,
telemetry, timeout, or cancellation contracts. See the
[Capability Execution Pipeline Guide](docs/CAPABILITY_EXECUTION_PIPELINE.md).

Ordered provider-neutral capability middleware can now surround that execution
boundary for both asynchronous results and complete streaming lifecycles.
Middleware receives immutable resolved invocation metadata, can continue once
or short-circuit, and inherits deterministic context and stream cleanup without
changing default applications. See the
[Capability Middleware Guide](docs/CAPABILITY_MIDDLEWARE.md).

Registered capabilities can optionally own application-scoped resources
through deterministic startup, reverse shutdown, partial-startup rollback,
bounded cleanup, and privacy-safe operational failures. Ordinary capabilities
remain unchanged. See the
[Capability Lifecycle Management Guide](docs/CAPABILITY_LIFECYCLE.md).

### Container quick start

Build and validate the production image:

```bash
docker build --tag trussium:local .
scripts/container-smoke-test.sh
```

Run it with hardened defaults:

```bash
docker run --rm \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  --cap-drop ALL \
  --security-opt no-new-privileges:true \
  --publish 9000:9000 \
  trussium:local
```

### Kubernetes quick start

Validate and deploy the release-pinned production overlay:

```bash
scripts/kubernetes-validate.sh
kubectl apply -k deploy/kubernetes/overlays/production
```

The published GHCR package currently requires an image-pull Secret. See the
[Kubernetes Deployment Guide](docs/KUBERNETES.md) for private-registry setup,
provider configuration, customization, validation, upgrades, and rollback.

For configurable installation and Helm-managed upgrades, use the independently
versioned official [`trussium` chart](https://github.com/trussiumhq/trussium-helm):

```bash
helm registry login ghcr.io --username YOUR_GITHUB_USERNAME
helm install trussium \
  oci://ghcr.io/trussiumhq/charts/trussium \
  --version 0.4.8 \
  --namespace trussium-system
```

Chart v0.4.8 defaults to runtime v0.39.0, enables the production CPU
autoscaler and runtime metrics contract, and exposes schema-validated
dependency-readiness settings with safe disabled defaults. It also exposes
schema-validated OpenTelemetry tracing values while keeping trace export
disabled until an operator supplies a reachable collector endpoint. The chart requires a working
Kubernetes Metrics API by default; fixed replicas remain available by disabling
autoscaling. It deploys the runtime only and installs neither a collector nor
the future Trussium Operator.

---

## Documentation

Project documentation is available in the `docs/` directory.

- [Vision](docs/VISION.md)
- [Architecture](docs/ARCHITECTURE.MD)
- [Roadmap](docs/ROADMAP.md)
- [Runtime Metrics Guide](docs/METRICS.md)
- [OpenTelemetry Tracing Guide](docs/TRACING.md)
- [Structured Operational Logging Guide](docs/OPERATIONAL_LOGGING.md)
- [Runtime Dashboards Guide](docs/DASHBOARDS.md)
- [Runtime Alerting and Runbook Guide](docs/ALERTING.md)
- [Runtime Health and Dependency Readiness Guide](docs/HEALTH.md)
- [Runtime Service Lifecycle Guide](docs/LIFECYCLE.md)
- [Runtime Service Registry Guide](docs/SERVICE_REGISTRY.md)
- [Runtime Component Health Reporting Guide](docs/COMPONENT_HEALTH.md)
- [Core Capability Registry Guide](docs/CAPABILITY_REGISTRY.md)
- [Capability Metadata and Discovery Guide](docs/CAPABILITY_DISCOVERY.md)
- [Capability Execution Pipeline Guide](docs/CAPABILITY_EXECUTION_PIPELINE.md)
- [Capability Middleware Guide](docs/CAPABILITY_MIDDLEWARE.md)
- [Capability Lifecycle Management Guide](docs/CAPABILITY_LIFECYCLE.md)
- [Runtime Exception Hierarchy Guide](docs/ERRORS.md)
- [Python Packaging Guide](docs/PACKAGING.md)
- [Container Guide](docs/CONTAINERS.md)
- [Kubernetes Deployment Guide](docs/KUBERNETES.md)
- [Official Helm Chart](https://github.com/trussiumhq/trussium-helm)
- [Graceful Shutdown Guide](docs/SHUTDOWN.md)
- Architecture Decision Records (ADRs) *(coming soon)*

A dedicated documentation site will be published as the project matures.

---

## Roadmap

Trussium will evolve through the following milestones:

- Runtime Foundation
- AI Runtime
- Agent Runtime
- Cloud-Native Platform

For a detailed roadmap, planned milestones, and project progress, see **[docs/ROADMAP.md](docs/ROADMAP.md)**.

---

## Contributing

Contributions, discussions, ideas, and design feedback are welcome.

As the project matures, contribution guidelines, issue templates, governance documentation, and a code of conduct will be added.

---

## License

Licensed under the Apache License 2.0.

---

## Philosophy

AI providers will evolve.

Models will change.

Protocols will emerge.

Applications should not need to change every time the AI ecosystem does.

Trussium's goal is to provide a stable, extensible runtime that enables developers to build AI applications once and run them across any provider, protocol, or deployment environment.
