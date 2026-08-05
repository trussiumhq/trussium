# Roadmap

_Last updated: August 2026_

This roadmap outlines the long-term direction of Trussium.

It communicates the major product and engineering milestones guiding the project. Individual implementation tasks, bugs, and feature requests are tracked separately through GitHub Issues and Projects.

The roadmap is intentionally high level and may evolve as the project, community, and commercial use cases mature.

---

## Current Focus

Trussium now has its first provider-neutral AI execution path:

```text
Client
  → REST API
  → Normalized chat capability
  → Provider adapter
  → OpenAI Responses API
  → Normalized JSON or SSE response
```

Both streaming and non-streaming requests use normalized provider errors. Every HTTP request has request and execution identifiers and emits structured JSON lifecycle logs containing its correlation metadata, HTTP method, path, status code, and duration.

The runtime now propagates immutable execution context across asynchronous and streaming workflows. Structured logs automatically inherit available request, execution, capability, provider, and model fields. Capability and provider executions emit separately correlated structured lifecycle events across both non-streaming and streaming workflows. Active streams detect client disconnects, promptly release upstream resources, and emit correlated cancellation lifecycles. The immediate focus is timeout handling and end-to-end validation.

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
- Conventional Commits
- Semantic Versioning
- Automated version calculation
- Automated Git tags
- Automated GitHub Releases
- Automated changelog generation
- Dependabot configuration

### Remaining

- Verify complete CodeQL coverage
- Verify dependency vulnerability scanning
- Verify secret-scanning configuration
- Verify release automation across supported release scenarios
- Document release recovery procedures
- Add package build and installation validation

This milestone can be marked completed once every listed automation is active, verified, and documented in the repository.

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
- Provider-neutral capability execution errors
- Protocol-neutral capability error categories
- Request-correlation middleware
- Request-scoped correlation context using `ContextVar`
- Caller-provided `X-Request-ID` support
- Generated UUID request identifiers
- Correlation identifiers on HTTP responses
- Request correlation preserved during streaming execution
- Request context cleanup after request processing
- Immutable typed execution context
- Internal UUID execution identifiers for HTTP requests
- Scoped capability, provider, and model context binding
- Nested execution-context inheritance and restoration
- Execution-context propagation across asynchronous tasks
- Execution-context propagation during streaming execution
- Execution-context cleanup after request processing
- Central structured logging configuration
- Structured JSON log formatter
- Namespaced Trussium loggers
- Automatic structured-log enrichment from runtime context
- Explicit structured-log field precedence over inherited context
- Structured HTTP request lifecycle middleware
- Request-started lifecycle events
- Request-completed lifecycle events
- Request-failed lifecycle events
- Request duration measurement
- Request ID correlation in HTTP lifecycle logs
- Provider-neutral capability logging decorator
- Capability execution-started lifecycle events
- Capability execution-completed lifecycle events
- Capability execution-failed lifecycle events
- Capability execution duration measurement
- Capability, model, and streaming-mode log fields
- Normalized capability error-code log fields
- Full streaming-iterator lifecycle logging
- Reusable provider execution logging decorator
- Provider execution-started lifecycle events
- Provider execution-completed lifecycle events
- Provider execution-failed lifecycle events
- Provider execution duration measurement
- Provider, model, and streaming-mode log fields
- Normalized provider error-code log fields
- Nested capability and provider lifecycle correlation
- Pure-ASGI client-disconnect detection
- Structured HTTP request-cancelled lifecycle events
- Capability execution-cancelled lifecycle events
- Provider execution-cancelled lifecycle events
- Stable cancellation-reason log fields
- Cooperative cancellation propagation
- Prompt asynchronous iterator finalization

### Remaining

- Unified runtime exception hierarchy
- Lifecycle hooks for runtime services
- Core runtime service registry
- Graceful shutdown validation
- Runtime startup diagnostics
- Runtime component health reporting

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
- Provider-neutral execution failure contract
- Protocol-independent error classification
- Provider-neutral structured capability lifecycle logging
- Capability execution duration measurement
- Streaming execution lifecycle logging through iterator exhaustion

### Remaining

- Capability registry
- Capability discovery
- Capability execution pipeline
- Capability middleware
- Capability lifecycle management
- Capability metadata
- Capability availability reporting
- Capability health reporting
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
- Quota error classification
- Rate-limit error classification
- Authentication error classification
- Permission error classification
- Timeout error classification
- Connection error classification
- Safe client-facing provider error messages
- Shared error normalization for streaming and non-streaming execution
- Provider adapter unit tests
- Reusable provider execution logging decorator
- Structured provider execution lifecycle events
- Provider execution duration measurement
- Full streaming-iterator provider lifecycle logging
- Stable normalized provider error-code logging
- OpenAI runtime logging composition
- OpenAI streaming connection release during cancellation

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
- Provider capability reporting
- Provider credential validation

The next provider should validate that Trussium’s abstractions are genuinely provider-neutral rather than OpenAI-specific.

A self-hosted OpenAI-compatible provider such as vLLM or Ollama may provide stronger architectural validation than adding several managed providers immediately.

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
- OpenAI streaming integration
- Incomplete-stream termination handling
- Missing-provider service errors
- Unified non-streaming provider error responses
- Provider-neutral HTTP status mapping
- Capability error category to HTTP status mapping
- Quota failures mapped to HTTP 503
- Temporary rate limits mapped to HTTP 429
- Provider authentication and connection failures mapped to HTTP 502
- Provider timeouts mapped to HTTP 504
- Safe API error messages
- `X-Request-ID` propagation on successful responses
- `X-Request-ID` propagation on HTTP error responses
- Request identifiers on health responses
- Request identifiers on active SSE responses
- Caller-provided request identifiers
- Generated request identifiers
- Request-scoped correlation context during streaming
- Internal execution identifiers for every HTTP request
- Typed request and execution context
- Capability, provider, and model execution metadata
- Nested execution-context binding and restoration
- Asynchronous task context propagation
- Streaming execution-context propagation
- Automatic runtime-context enrichment for structured logs
- Structured request-started logs
- Structured request-completed logs
- Structured request-failed logs
- Request ID, method, path, status, and duration log fields
- OpenAPI documentation
- Provider error response documentation
- API unit tests
- Streaming API tests
- HTTP error-mapping tests
- Request-correlation middleware tests
- Structured request-logging tests
- Structured provider execution logging
- Correlated capability and provider lifecycle ordering
- Streaming provider lifecycle logging
- Client-disconnect detection for active SSE streams
- Stream cancellation propagation
- Structured HTTP, capability, and provider cancellation events
- Prompt provider stream finalization
- ASGI 2.3 and ASGI 2.4 disconnect handling

### Remaining

- Stream timeout handling
- Non-streaming request timeout handling
- Consistent error envelopes across validation and runtime failures
- Model aliasing
- Request validation refinements
- API versioning policy
- End-to-end integration tests
- Example client application
- Production-oriented API documentation

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
- Idempotency considerations
- Retry budget controls

Deterministic routing should be implemented and measured before introducing advanced or AI-assisted routing strategies.

---

## Milestone 8 — Identity, Governance, and Usage Controls

**Status:** 🗓 Planned

Provide the controls required for secure organizational and enterprise use.

### Deliverables

- Runtime API keys
- Tenant identity
- Project identity
- Application identity
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
- Tenant-aware provider policies
- Usage export interfaces

This milestone is required before positioning Trussium as a production governance or multi-tenant AI platform.

---

## Milestone 9 — Cloud-Native Operations

**Status:** 🗓 Planned

Make Trussium deployable and operable across modern cloud-native environments.

### Deliverables

- Production Docker image
- Kubernetes manifests
- Helm chart
- ConfigMap integration
- Secret integration
- Horizontal scaling
- Graceful termination
- Pod disruption support
- OpenTelemetry instrumentation
- Prometheus metrics
- Distributed tracing
- Structured operational logs
- Runtime dashboards
- Alerting guidance
- Readiness dependency checks
- Production deployment documentation
- Upgrade and rollback procedures

Health checks and structured HTTP lifecycle logs have already been delivered as part of the runtime foundation.

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
- API usage examples
- Troubleshooting guide

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
- Execution limits
- Agent policy enforcement

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

gRPC and MCP should reuse the same capability, provider, execution, and error contracts rather than introducing separate runtime paths.

The HTTP API should remain the primary integration surface until its request, response, streaming, error, authentication, and versioning contracts are stable.

---

## Guiding Principles

The roadmap is guided by the following principles:

- Cloud-native by design
- Provider-neutral contracts
- Capability-first architecture
- Protocol-independent execution
- Protocol-neutral error classification
- Extensible provider and plugin model
- Observable by default
- Structured machine-readable logs
- Request correlation by default
- Secure by default
- Explicit tenant and usage boundaries
- Reliable failure handling
- Safe client-facing errors
- Developer-focused integration
- Backwards-compatible public interfaces
- Incremental, customer-testable delivery
- Operational simplicity before architectural breadth

---

## Release Strategy

Trussium follows Semantic Versioning and Conventional Commits.

Project releases are automated through GitHub Actions and include:

- Automated quality validation
- Automated changelog generation
- Version tags
- GitHub Releases
- Dependency updates
- Release notes derived from conventional commits

Future release improvements should include:

- Upgrade notes for breaking changes
- Release recovery procedures
- Package installation validation
- Compatibility guarantees for public interfaces
- Independent versioning for separately released repositories

Public interface stability should be clearly documented before the first stable release.

---

## Immediate Priorities

The next priorities for the first chat vertical slice are:

1. Add provider and stream timeout handling
2. Add end-to-end integration testing
3. Validate a self-hosted model provider
4. Add production container packaging

These priorities strengthen Trussium’s observability, reliability, and operability before expanding into routing, governance, additional protocols, or additional AI capabilities.

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
- Hosted management plane
- Community-contributed providers and plugins

These items are exploratory and do not represent committed deliverables.
