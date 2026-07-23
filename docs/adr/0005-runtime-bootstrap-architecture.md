# ADR 0011 — Runtime Bootstrap Architecture

**Status:** Accepted

**Date:** 2026-07-23

---

# Context

Trussium is being developed as a cloud-native AI runtime capable of integrating multiple providers while remaining modular, testable, and deployment-friendly.

Before implementing runtime functionality, the project requires a documented architectural foundation that defines package responsibilities, dependency boundaries, and application composition.

Without these decisions, future implementation risks inconsistent structure, tight coupling, and architectural drift.

---

# Decision

Trussium will adopt a layered architecture with a dedicated application composition root.

The runtime will be organized around clearly defined package boundaries where each package owns a single responsibility.

The application entry point will compose the system while individual packages remain independent and reusable.

---

# Architecture

```
                 Application
                      │
         ┌────────────┼────────────┐
         │            │            │
      API Layer   Runtime Layer   Config
         │            │            │
         └────────────┼────────────┘
                      │
               Provider Contracts
                      │
          ┌───────────┼────────────┐
          │           │            │
      OpenAI     Anthropic     Ollama
```

---

# Package Structure

```
src/trussium/

├── app/
├── api/
├── runtime/
├── config/
├── providers/
├── plugins/
├── telemetry/
├── security/
├── storage/
├── models/
└── cli/
```

---

# Package Responsibilities

## app

Application composition root.

Responsibilities include:

- dependency wiring
- runtime initialization
- configuration loading
- logging initialization
- telemetry initialization
- FastAPI application creation
- provider registration
- startup and shutdown lifecycle

No business logic should exist here.

---

## runtime

Contains the runtime orchestration logic.

Responsible for:

- application lifecycle
- execution flow
- runtime services
- coordination between components

The runtime must not depend on any specific AI provider.

---

## api

Responsible for HTTP concerns only.

Includes:

- routers
- middleware
- request models
- response models
- exception handlers

Business logic should remain outside this package.

---

## config

Responsible for configuration management.

Includes:

- environment loading
- validation
- defaults
- configuration models

---

## providers

Contains implementations of external AI providers.

Each provider must implement the same contract.

Examples include:

- OpenAI
- Anthropic
- Ollama
- Gemini
- Azure OpenAI

---

## plugins

Future plugin discovery mechanism.

External extensions should integrate through this package.

---

## telemetry

Provides observability.

Responsibilities:

- structured logging
- metrics
- distributed tracing

---

## security

Authentication and authorization.

Future responsibilities include:

- API keys
- OAuth
- RBAC
- JWT validation

---

## storage

Persistence abstractions.

Examples:

- Redis
- PostgreSQL
- object storage

---

## models

Shared domain models.

These models should remain independent from transport protocols.

---

## cli

Command-line interface.

Provides commands for:

- starting the runtime
- validation
- diagnostics
- administration

---

# Dependency Rules

The following dependency rules apply.

```
app
 │
 ├── api
 ├── runtime
 ├── config
 │
runtime
 │
providers

telemetry

storage
```

Rules:

- app may depend on every package.
- api must never depend on provider implementations.
- providers must never depend on FastAPI.
- runtime must not depend on HTTP.
- configuration must not depend on runtime.
- circular dependencies are prohibited.

---

# Alternatives Considered

## Monolithic architecture

Rejected due to tight coupling and poor extensibility.

## Feature-first organization

Rejected because infrastructure concerns would become duplicated across packages.

## Provider-specific runtime

Rejected because the runtime should remain provider-agnostic.

---

# Consequences

Positive:

- clear package boundaries
- improved maintainability
- easier testing
- extensibility
- contributor guidance

Trade-offs:

- additional initial structure
- slightly more upfront design

The long-term benefits outweigh the initial complexity.

---

# Future Work

Future ADRs will define:

- provider interface
- plugin system
- configuration model
- runtime lifecycle
- dependency injection
- Kubernetes deployment architecture
- distributed runtime
- gRPC support
- MCP support

---

# References

- ADR 0001 — Project Vision
- ROADMAP.md
- ARCHITECTURE.md
