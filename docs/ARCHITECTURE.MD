# Trussium Architecture

> **Status:** Draft
>
> This document describes the architectural vision for Trussium.
> It serves as the primary technical reference for the project and guides implementation decisions as the platform evolves.

---

# Overview

Trussium is a cloud-native runtime for AI applications.

Its primary responsibility is to provide a consistent execution layer between AI applications and the rapidly evolving ecosystem of AI providers, protocols, tools, and deployment platforms.

Applications integrate with Trussium once.

Trussium manages communication with providers, execution of capabilities, routing, observability, and future extensions.

---

# Architectural Principles

The architecture is guided by the following principles:

- Cloud-native by design
- Provider agnostic
- Capability first
- Protocol agnostic
- Extensible through plugins
- Observable by default
- Secure by default
- API-first
- Backwards-compatible public interfaces

---

# High-Level Architecture

```text
                    AI Applications
                           │
        REST        gRPC        MCP
             \        │        /
              \       │       /
               Trussium Runtime
                      │
              Runtime Services
                      │
             Capability Framework
                      │
              Provider Adapters
                      │
  OpenAI • Anthropic • Gemini • Ollama • ...
```

The runtime is responsible for orchestrating requests while remaining independent of provider-specific implementations.

---

# Runtime Layers

The runtime is organized into logical layers.

```text
┌────────────────────────────────────┐
│           API Layer                │
├────────────────────────────────────┤
│         Runtime Services           │
├────────────────────────────────────┤
│      Capability Framework          │
├────────────────────────────────────┤
│       Provider Adapters            │
├────────────────────────────────────┤
│      Infrastructure Layer          │
└────────────────────────────────────┘
```

Each layer has a clearly defined responsibility and communicates only with adjacent layers.

---

# API Layer

The API layer exposes Trussium through multiple protocols.

Supported interfaces include:

- REST
- gRPC
- Model Context Protocol (MCP)

Future protocols can be added without modifying the runtime.

---

# Runtime Services

Runtime Services coordinate request execution.

Responsibilities include:

- Request orchestration
- Authentication
- Authorization
- Routing
- Retry policies
- Failover
- Rate limiting
- Streaming
- Request lifecycle management

Runtime Services are provider independent.

---

# Capability Framework

The Capability Framework defines what Trussium can execute.

Examples include:

- Chat
- Embeddings
- Image Generation
- Audio
- Video
- Realtime
- Tool Execution
- Agents

Capabilities define the runtime contract.

Providers implement capabilities.

Application composition registers provider-neutral implementations under
validated stable capability names. A sealed insertion-ordered registry owns
local lookup and immutable discovery, while protocol-specific execution remains
behind capability interfaces. The REST API resolves `chat.completions` through
that registry rather than a dedicated provider attribute. Bounded immutable
metadata travels with registrations and powers the ordered read-only
`GET /v1/capabilities` discovery view without exposing implementations,
providers, models, health, or availability.

A separate reporter binds to the sealed source registry and gives every
registration an informational availability state. Optional capability checks
run concurrently within a dedicated deadline and feed the ordered
`GET /v1/capabilities/availability` view without gating execution, liveness, or
readiness.

One application-owned execution pipeline sits on top of the sealed registry.
It resolves canonical names once, binds immutable execution context across
non-streaming and streaming work, preserves capability-specific results and
failures, and finalizes upstream streams. The existing chat REST path uses this
boundary without moving transport, logging, tracing, timeout, or provider
semantics into the pipeline.

An immutable ordered middleware snapshot surrounds that execution boundary.
Each provider-neutral layer receives frozen resolved invocation metadata and a
single-use continuation for asynchronous or streaming work. Declaration-order
entry, reverse unwind, short-circuiting, context propagation, and pipeline-owned
stream cleanup are shared across capability interfaces. Lifecycle management,
availability reporting, health, routing, provider registration, and dynamic
plugins remain separate framework layers.

---

# Provider Adapters

Provider adapters translate runtime requests into provider-specific APIs.

Examples include:

- OpenAI
- Anthropic
- Google Gemini
- Ollama
- Amazon Bedrock
- Azure OpenAI

Adapters isolate provider-specific behavior from the rest of the runtime.

---

# Infrastructure Layer

Infrastructure components support the runtime.

Responsibilities include:

- Configuration
- Logging
- Metrics
- Tracing
- Secrets
- Dependency injection
- Lifecycle management

These components remain independent of runtime capabilities.

---

# Request Lifecycle

Every request follows a consistent execution pipeline.

```text
Client
   │
API Layer
   │
Authentication
   │
Authorization
   │
Routing
   │
Capability Framework
   │
Provider Adapter
   │
AI Provider
   │
Response
```

This lifecycle remains consistent regardless of provider or protocol.

---

# Plugin Architecture

Trussium is designed to be extensible.

Extension points include:

- Providers
- Capabilities
- Middleware
- Routing strategies
- Authentication
- Authorization
- Observability

Plugins should be discoverable without modifying the runtime.

---

# Repository Strategy

The Trussium project consists of multiple repositories.

```text
Trussium
│
├── trussium
├── trussiumctl
├── trussium-helm
├── trussium-operator
├── trussiumhq.github.io
├── trussium-sdk-python
├── trussium-sdk-go
├── trussium-sdk-typescript
├── trussium-provider-vllm
├── trussium-provider-anthropic
├── trussium-provider-libretranslate
└── trussium-provider-piper
```

Each repository has a clearly defined responsibility and independent release
cadence. The runtime is the core Python platform; Helm and the operator own
Kubernetes packaging and lifecycle management; the documentation site publishes
assembled project docs; SDKs provide language-specific clients; and provider
repositories contain optional adapters that translate external APIs into the
runtime's provider-neutral contracts.

`trussiumctl` is the standalone Go platform CLI. It coordinates Kubernetes and
Helm operations through documented APIs and published artifacts; it does not
embed runtime execution or provider SDKs.

---

# Technology Strategy

Languages are selected based on the responsibilities of each component.

| Component | Language |
|-----------|----------|
| Runtime | Python |
| Runtime CLI | Python |
| Platform CLI (`trussiumctl`) | Go |
| Kubernetes Operator | Go |
| SDK (Python) | Python |
| SDK (Go) | Go |
| SDK (TypeScript) | TypeScript |

Each language is chosen to best suit the operational characteristics of the component.

---

# Deployment Model

Trussium is designed to run in multiple environments.

- Local development
- Docker
- Kubernetes
- Managed cloud platforms

The runtime should behave consistently across all supported deployment environments.

---

# Design Philosophy

The architecture favors stable abstractions over provider-specific implementations.

Provider APIs will continue to evolve.

New protocols will emerge.

New AI capabilities will be introduced.

The runtime should absorb ecosystem changes without requiring applications to change.

Applications integrate once.

Trussium evolves behind the interface.
