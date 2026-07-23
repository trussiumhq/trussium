# ADR-0003: Capability-First Architecture

**Status:** Accepted

**Date:** 2026-07-23

**Related Documents:**

- ARCHITECTURE.md
- ROADMAP.md

**Supersedes:** None

---

# Context

The AI ecosystem is evolving rapidly.

New providers, models, protocols, and AI capabilities are introduced regularly. While providers differ in implementation, many expose similar capabilities such as conversational AI, embeddings, image generation, audio processing, and real-time interactions.

Traditional AI frameworks typically organize their architecture around providers. Applications interact with provider-specific implementations, requiring the runtime to understand the differences between each provider.

As the number of providers and capabilities grows, this approach increases coupling between the runtime and provider implementations.

A more extensible architectural model is required.

---

# Decision

Trussium adopts a capability-first architecture.

The runtime is designed around AI capabilities rather than provider implementations.

Capabilities define the services available to applications.

Providers implement one or more capabilities through provider-specific adapters.

The runtime orchestrates capabilities without embedding provider-specific logic.

---

# Architecture

Instead of treating providers as the primary abstraction:

```text
Application
      │
      ▼
 OpenAI Provider
```

Trussium introduces an intermediate capability layer.

```text
Application
      │
      ▼
 Runtime
      │
      ▼
 Capability
      │
      ▼
 Provider Adapter
      │
      ▼
 AI Provider
```

Applications interact with capabilities.

Capabilities delegate execution to provider adapters.

---

# Capability Model

Capabilities represent categories of AI functionality.

Examples include:

- Chat
- Embeddings
- Image Generation
- Audio Processing
- Video Generation
- Real-time Communication
- Tool Execution
- Agent Execution

Capabilities describe *what* can be performed rather than *how* it is implemented.

---

# Provider Adapters

Providers implement one or more capabilities.

Examples:

```text
OpenAI

✓ Chat
✓ Embeddings
✓ Images
✓ Audio
✓ Realtime
```

```text
Anthropic

✓ Chat
✓ Tool Execution
```

```text
Ollama

✓ Chat
✓ Embeddings
```

The runtime determines whether a provider supports a capability rather than assuming feature parity across providers.

---

# Runtime Responsibilities

The runtime is responsible for:

- Request orchestration
- Capability discovery
- Routing
- Provider selection
- Authentication
- Authorization
- Observability
- Retry policies
- Streaming

The runtime does not contain provider-specific business logic.

---

# Extensibility

New providers are introduced by implementing existing capabilities.

New AI capabilities can be added without modifying existing providers.

For example, introducing a future "Video Generation" capability requires:

- Defining the capability.
- Implementing adapters for supporting providers.
- Registering the capability.

Existing runtime components remain unchanged.

---

# Benefits

A capability-first architecture provides:

- Provider independence
- Reduced coupling
- Improved extensibility
- Easier testing
- Consistent runtime interfaces
- Simplified onboarding of new providers

Applications remain insulated from changes in provider APIs.

---

# Consequences

## Positive

- Stable runtime interfaces.
- Easier provider integration.
- Support for heterogeneous provider capabilities.
- Reduced duplication across providers.
- Improved long-term maintainability.

## Negative

- Additional abstraction layer.
- Slight increase in architectural complexity.
- More initial design effort.
- Capability contracts must remain stable.

These trade-offs are acceptable in exchange for improved extensibility and maintainability.

---

# Alternatives Considered

## Option 1 — Provider-First Architecture

Applications communicate directly with provider implementations.

Advantages

- Simpler initial implementation.
- Fewer abstractions.
- Faster early development.

Rejected because:

- Runtime becomes provider-aware.
- Higher coupling.
- Difficult to support emerging capabilities.
- More duplication across providers.

---

## Option 2 — Capability-First Architecture

Applications communicate with capabilities.

Capabilities delegate execution to provider adapters.

Advantages

- Loose coupling.
- Extensible architecture.
- Stable public interfaces.
- Easier integration of future providers.
- Improved long-term maintainability.

Accepted.

---

# Compliance

All runtime functionality should be introduced through capabilities.

Provider-specific functionality should remain isolated within provider adapters.

Changes that introduce provider-specific logic into the runtime require a new Architecture Decision Record.
