# Roadmap

_Last updated: July 2026_

This roadmap outlines the long-term direction of Trussium.

It communicates the major product and engineering milestones guiding the project. Individual implementation tasks, bugs, and feature requests are tracked separately through GitHub Issues and Projects.

The roadmap is intentionally high level and may evolve as the project, community, and commercial use cases mature.

---

## Current Focus

Trussium is currently building its first complete provider-neutral AI execution path:

```text
Client
  → REST API
  → Normalized chat capability
  → Provider adapter
  → OpenAI Responses API
  → Normalized JSON or SSE response
```

The immediate objective is to make this path reliable, observable, testable, and suitable for self-hosted deployments before expanding into additional capabilities and protocols.

---

## Status Definitions

- ✅ **Completed** — The milestone’s core completion criteria have been delivered.
- 🚧 **In Progress** — Implementation has started, but significant deliverables remain.
- 🗓 **Planned** — The milestone is accepted but implementation has not substantially started.
- ⏸ **Deferred** — Intentionally postponed until prerequisite milestones are stable.

---

## Milestone 1 — Project Foundation

**Status:** ✅ Completed

Establish the project’s vision, architecture, documentation, and contribution standards.

### Delivered

- Project documentation
- Product vision
- Initial roadmap
- Architecture documentation
- Architecture Decision Records
- Repository standards
- Contributing guide
- Development guide
- Code of Conduct
- Security policy
- Changelog structure

---

## Milestone 2 — Engineering Platform

**Status:** 🚧 In Progress

Establish a dependable engineering workflow for local development, continuous integration, security, and releases.

### Delivered

- Ruff formatting and linting
- Strict MyPy type checking
- Pytest test suite
- Coverage support
- Pre-commit workflow
- Python package structure
- Automated build and test validation

### Remaining

- Verify complete CodeQL coverage
- Verify dependency vulnerability scanning
- Verify secret-scanning configuration
- Complete release automation
- Automated changelog generation
- Automated version tagging
- Automated GitHub Releases

This milestone can be marked completed once every listed automation is active and verified in the repository.

---

## Milestone 3 — Runtime Foundation

**Status:** 🚧 In Progress

Build the foundational runtime components required by capabilities, providers, APIs, and future plugins.

### Delivered

- Environment-based configuration system
- Application composition root
- Dependency injection for runtime capabilities
- Application startup entry point
- Runtime configuration overrides
- Liveness health endpoint
- Readiness health endpoint
- Core application lifecycle integration

### Remaining

- Structured logging
- Request and execution context
- Correlation and request identifiers
- Unified runtime exception framework
- Lifecycle hooks for runtime services
- Core runtime service registry
- Graceful shutdown validation

---

## Milestone 4 — Capability Framework

**Status:** 🚧 In Progress

Define provider-neutral contracts through which AI functionality is exposed.

### Delivered

- Normalized chat-completion request contract
- Normalized chat-completion response contract
- Normalized token usage contract
- Normalized finish reasons
- Normalized streaming event contracts
- `ChatCapability` protocol
- Non-streaming capability execution
- Streaming capability execution

### Remaining

- Capability registry
- Capability discovery
- Capability execution pipeline
- Capability middleware
- Capability lifecycle management
- Capability metadata
- Capability availability reporting
- Additional capability interfaces

The capability framework should not be marked completed until capabilities can be registered, discovered, and executed without direct application wiring.

---

## Milestone 5 — Provider Framework

**Status:** 🚧 In Progress

Enable AI providers to implement Trussium capabilities through isolated adapters.

### Delivered

- OpenAI chat capability adapter
- OpenAI Responses API integration
- Normalized request translation
- Normalized non-streaming responses
- Normalized streaming events
- Incomplete-response handling
- Provider error normalization
- Quota, authentication, permission, timeout, connection, and rate-limit error mapping
- Provider adapter unit tests

### Remaining

- Provider interface and metadata contract
- Provider registry
- Provider configuration
- Provider discovery
- Provider lifecycle management
- Plugin loading
- Model availability discovery
- Self-hosted model adapter
- At least one additional managed provider
- Provider health reporting

The next provider should validate that Trussium’s abstractions are genuinely provider-neutral rather than OpenAI-specific.

---

## Milestone 6 — Chat Runtime and HTTP API

**Status:** 🚧 In Progress

Deliver the first complete, customer-testable Trussium runtime workflow.

### Delivered

- `POST /v1/chat/completions`
- Provider-neutral chat execution
- Normalized JSON responses
- Server-Sent Events streaming
- Normalized `start`, `delta`, `end`, and `error` events
- Missing-provider service errors
- OpenAPI documentation
- API unit tests
- Streaming API tests

### Remaining

- Unified non-streaming provider error responses
- Client-disconnect and cancellation handling
- Stream timeout handling
- Request identifiers
- Consistent API error envelope
- Model aliasing
- Request validation refinements
- API versioning policy
- End-to-end integration tests
- Example client application

This milestone represents Trussium’s first usable vertical slice and should be completed before expanding into several additional model capabilities.

---

## Milestone 7 — Routing and Resilience

**Status:** 🗓 Planned

Enable Trussium to select providers and recover from provider failures.

### Deliverables

- Model and provider routing
- Static routing policies
- Provider priority configuration
- Retry policies
- Timeout policies
- Provider fallback
- Model fallback
- Circuit breaking
- Health-aware routing
- Routing decision metadata
- Failure classification
- Routing telemetry

Advanced AI-based routing should be considered only after deterministic routing is reliable and measurable.

---

## Milestone 8 — Identity, Governance, and Usage Controls

**Status:** 🗓 Planned

Provide the controls required for secure organizational and enterprise use.

### Deliverables

- Runtime API keys
- Tenant identity
- Project and application identity
- Authentication
- Authorization
- Rate limiting
- Usage metering
- Token accounting
- Tenant quotas
- Budget limits
- Audit events
- Request attribution
- Provider credential isolation

This milestone is required before positioning Trussium as a production governance or multi-tenant AI platform.

---

## Milestone 9 — Cloud-Native Operations

**Status:** 🗓 Planned

Make Trussium deployable and operable across modern cloud-native environments.

### Deliverables

- Production Docker image
- Kubernetes manifests
- Helm chart
- ConfigMap and Secret integration
- Horizontal scaling
- Graceful termination
- Pod disruption support
- OpenTelemetry instrumentation
- Prometheus metrics
- Distributed tracing
- Structured operational logs
- Runtime dashboards
- Alerting guidance
- Production deployment documentation

Health checks have already been delivered as part of the runtime foundation.

---

## Milestone 10 — Developer Experience and Ecosystem

**Status:** 🗓 Planned

Make Trussium easy to install, integrate, extend, and operate.

### Deliverables

- Command-line interface
- Python SDK
- Go SDK
- TypeScript SDK
- Example applications
- Project templates
- Provider development guide
- Capability development guide
- Plugin development kit
- Integration documentation
- Local development environment
- Community provider plugins

SDK development should follow a stable HTTP API rather than preceding it.

---

## Milestone 11 — Additional AI Capabilities

**Status:** ⏸ Deferred

Expand the runtime after the chat execution path, routing, identity, telemetry, and deployment experience are stable.

### Potential Deliverables

- Embeddings
- Image generation
- Audio processing
- Video processing
- Reranking
- Moderation
- Tool execution
- Batch inference

Each capability should be introduced as a complete vertical slice with contracts, provider adapters, APIs, telemetry, tests, and documentation.

---

## Milestone 12 — Agent Runtime

**Status:** ⏸ Deferred

Extend Trussium beyond model inference into controlled workflow and agent execution.

### Potential Deliverables

- Tool contracts
- Tool execution
- Workflow orchestration
- Agent execution
- Multi-agent communication
- Memory interfaces
- Agent lifecycle management
- MCP-native execution
- Human approval workflows
- Execution auditing

Agent functionality should not be prioritized until the underlying runtime, governance, routing, and observability layers are production-ready.

---

## Protocol Strategy

Trussium remains protocol-agnostic, but protocols will be introduced according to demonstrated user needs.

### Current

- REST
- Server-Sent Events

### Planned

- Model Context Protocol

### Deferred

- gRPC

gRPC and MCP should be implemented after the core HTTP and streaming contracts are stable. They should reuse the same capability and provider layers rather than creating separate execution paths.

---

## Guiding Principles

The roadmap is guided by the following principles:

- Cloud-native by design
- Provider-neutral contracts
- Capability-first architecture
- Protocol-independent execution
- Extensible provider and plugin model
- Observable by default
- Secure by default
- Explicit tenant and usage boundaries
- Reliable failure handling
- Developer-focused integration
- Backwards-compatible public interfaces
- Incremental, customer-testable delivery

---

## Release Strategy

Trussium follows Semantic Versioning and Conventional Commits.

Releases should include:

- Automated quality validation
- Automated changelog generation
- Version tags
- GitHub Releases
- Upgrade notes for breaking changes
- Independent versioning for separately released repositories

Public interface stability should be clearly documented before the first stable release.

---

## Future Exploration

Future milestones may include:

- Distributed execution
- Multi-cluster support
- Edge deployments
- GPU workload integration
- Cost-aware routing
- Latency-aware routing
- Regional data residency
- Federated runtimes
- Private model management
- Advanced policy engines
- Enterprise control plane
- Community-contributed providers and plugins

These items are exploratory and do not represent committed deliverables.
