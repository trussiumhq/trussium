# Trussium

> **Cloud-Native AI Runtime Platform**

Build AI applications once. Deploy anywhere. Connect to any model.

[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![gRPC](https://img.shields.io/badge/gRPC-first-4285F4)
![FastAPI](https://img.shields.io/badge/FastAPI-supported-009688)

---

## Vision

Trussium is a cloud-native AI runtime designed to provide a unified interface for AI applications regardless of the underlying model provider, protocol, or deployment environment.

Whether you're building with OpenAI, Anthropic, Gemini, Ollama, vLLM, or future AI providers, Trussium gives you a consistent, high-performance runtime for inference, streaming, observability, and governance.

Our mission is simple:

> **Build once. Run anywhere. Connect every AI provider.**

---

## Why Trussium?

Today's AI ecosystem is fragmented.

Every provider exposes different APIs.

Every framework introduces another abstraction.

Every deployment environment requires different integration logic.

As organizations adopt multiple AI providers, maintaining applications becomes increasingly complex.

Trussium solves this by acting as a unified AI runtime.

Instead of applications integrating directly with every model provider, they integrate once with Trussium.

```
Application
      │
      ▼
  Trussium Runtime
      │
 ┌────┴────────────────────────────────────┐
 │                                         │
OpenAI  Anthropic  Gemini  Ollama  Azure OpenAI
```

Applications become provider-agnostic.

---

## Core Principles

- **Provider Agnostic** – Switch providers without changing application code.
- **gRPC First** – High-performance streaming APIs with REST compatibility.
- **Cloud Native** – Built for Kubernetes and modern infrastructure.
- **Protocol Agnostic** – Support gRPC, REST, and Model Context Protocol (MCP).
- **Observability Built-in** – Metrics, tracing, and structured logging from day one.
- **Production Ready** – Designed for enterprise workloads.

---

## Features (Roadmap)

### Runtime

- Unified AI Runtime
- Multi-provider support
- Streaming inference
- Async execution
- Request routing

### Providers

- OpenAI
- Anthropic
- Google Gemini
- Ollama
- Azure OpenAI
- Amazon Bedrock
- vLLM

### APIs

- gRPC
- REST
- MCP

### Infrastructure

- Docker
- Kubernetes
- Helm
- Prometheus
- OpenTelemetry

### SDKs

- Python
- Go
- TypeScript

---

## Architecture

```
                 Client Applications
                         │
         ┌───────────────┴───────────────┐
         │                               │
      REST API                     gRPC API
         │                               │
         └───────────────┬───────────────┘
                         │
                 Trussium Runtime
                         │
          ┌──────────────┼──────────────┐
          │              │              │
     Provider Layer   Tool Layer     MCP Layer
          │
  ┌───────┼────────────────────────────────────┐
  │       │         │         │         │
OpenAI Anthropic Gemini Ollama Bedrock
```

---

## Planned Components

- Runtime
- Gateway
- Provider Framework
- Streaming Engine
- MCP Server
- Kubernetes Operator
- CLI
- SDKs

---

## Project Status

🚧 Early development

The project is under active development.

Expect breaking changes before the first stable release.

---

## Documentation

Documentation will be published at:

```
https://docs.trussium.dev
```

---

## Contributing

Contributions are welcome.

Please read our Contributing Guide before opening issues or pull requests.

---

## Roadmap

- [ ] Runtime foundation
- [ ] gRPC server
- [ ] FastAPI gateway
- [ ] Provider abstraction
- [ ] OpenAI provider
- [ ] Ollama provider
- [ ] Anthropic provider
- [ ] Streaming APIs
- [ ] MCP support
- [ ] Kubernetes deployment
- [ ] SDKs
- [ ] Trussium Cloud

---

## License

Apache License 2.0

---

## Philosophy

Infrastructure should make AI development simpler—not more complicated.

Trussium aims to become the runtime layer that standardizes how applications communicate with AI models, agents, tools, and future AI protocols.
