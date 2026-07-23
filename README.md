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

> **Note**
>
> The first runnable release is currently under construction.

---

## Documentation

Project documentation is available in the `docs/` directory.

- [Vision](docs/VISION.md)
- Architecture *(coming soon)*
- Roadmap *(coming soon)*
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
