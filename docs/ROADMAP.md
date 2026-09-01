# Roadmap

_Last updated: August 2026_

This roadmap outlines the long-term direction of Trussium.

It communicates the major product and engineering milestones guiding the project. Individual implementation tasks, bugs, and feature requests are tracked separately through GitHub Issues and Projects.

The roadmap is intentionally high level and may evolve as the project and community mature.

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

The runtime now propagates immutable execution context across asynchronous and streaming workflows. Structured logs automatically inherit available request, execution, capability, provider, and model fields. Capability and provider executions emit separately correlated structured lifecycle events across both non-streaming and streaming workflows. Active streams detect client disconnects, promptly release upstream resources, and emit correlated cancellation lifecycles. Trussium also enforces its own provider request deadlines and per-event stream-idle deadlines, independently of provider SDK defaults. A deterministic end-to-end suite validates the production process, real HTTP and SSE connections, OpenAI SDK boundary, normalized API contracts, correlated lifecycles, and bounded graceful shutdown without external services. Typed provider configuration selects OpenAI or Ollama while preserving legacy OpenAI environments, and live compatibility validation proves the same normalized path against a real self-hosted model. Trussium ships a hardened multi-platform production container with locked dependencies, non-root execution, OCI health metadata, real image smoke tests, automated GHCR publication, and configurable active-workload draining. Python wheels and source distributions are also built, inspected, installed into clean environments, exercised as real processes, and attached to semantic GitHub releases.

Production Kubernetes packaging now carries those contracts into a maintained Kustomize base and release-pinned production overlay. It provides hardened autoscaled pods, ConfigMap and optional Secret integration, private-GHCR authentication, health probes, resource boundaries, topology spreading, zero-unavailable rolling updates, disruption protection, graceful termination timing, release-version stamping, structural validation, and a real Kind-cluster smoke test. The runtime exposes app-scoped Prometheus-compatible Python, process, request-total, request-duration, and active-request metrics with bounded labels. Pure ASGI instrumentation measures complete JSON and streaming lifecycles, while the production `autoscaling/v2` HorizontalPodAutoscaler safely maintains two to ten replicas against live per-container CPU metrics. App-scoped OpenTelemetry SDK providers add inbound W3C context extraction, complete HTTP/capability/provider span hierarchies, parent-based sampling, OTLP HTTP/protobuf export, trace-correlated structured logs, bounded privacy-aware attributes, and clean exporter shutdown. W3C `traceparent` and optional `tracestate` now continue the active provider CLIENT span across OpenAI and Ollama-compatible JSON and SSE requests without global HTTP instrumentation. Unsampled decisions propagate correctly, while baggage, arbitrary headers, request IDs, payloads, and credentials remain behind the runtime privacy boundary. Tracing remains disabled by default until an operator supplies a reachable collector endpoint. Stable structured operational events now report bounded configuration summaries, provider configuration readiness, application and server lifecycle transitions, graceful-drain outcomes, and trace-export failures. Invalid settings and background failures expose only counts, error classes, and stable codes rather than rejected values, endpoints, exception text, payloads, or credentials.

The independently versioned [`trussium` Helm chart](https://github.com/trussiumhq/trussium-helm) packages the validated runtime contract for configurable installation, upgrades, and rollbacks. Its release target is updated alongside compatible runtime releases, enables runtime metrics and the production CPU autoscaler by default, and exposes schema-validated tracing and dependency-readiness values with safe disabled defaults. It exercises both configurations across autoscaled and fixed-replica Kind lifecycles and publishes GitHub and OCI artifacts without installing providers or observability backends. Three portable Grafana dashboards turn the stable Prometheus, structured-Loki, and Tempo contracts into independently importable operator views. A portable Prometheus starter profile adds bounded conditions for missing telemetry, sustained failures, cancellations, high p95 latency, and process restarts, with traffic guards, deterministic semantic tests, and complete runbooks. Opt-in dependency-aware readiness distinguishes fast local liveness from provider and optional required-model availability through bounded metadata checks, stable failure reasons, runtime-owned deadlines, monotonic caching, and single-flight refreshes. Trussium-owned failures share a public typed hierarchy with stable codes and bounded messages while native cancellation, validation, framework, and SDK boundaries remain intact. Application-scoped runtime services now use deterministic asynchronous startup, reverse shutdown, partial-startup rollback, bounded per-hook cleanup, and privacy-safe structured failure events. A sealed insertion-ordered runtime service registry now adds explicit registration, stable lookup, immutable discovery, duplicate protection, and lifecycle-backed application ownership. Registered services can now opt into bounded component health reporting with deterministic sealed-registry aggregation, deadlines, safe failure normalization, transition events, and an informational endpoint that remains separate from liveness and readiness. Provider-neutral capabilities now use a sealed insertion-ordered registry with canonical identities, explicit registration, stable lookup, immutable discovery, duplicate protection, safe contract validation, application-owned execution composition, and compatibility for existing chat factory callers. Bounded immutable metadata now travels with capability registrations and powers ordered external discovery through `GET /v1/capabilities` without exposing providers, models, implementations, health, availability, or configuration. A sealed-registry-backed capability execution pipeline now resolves canonical identities once, preserves immutable context and native failures, returns values and events unchanged, and closes upstream streams across complete asynchronous lifecycles. Ordered provider-neutral capability middleware now supplies immutable invocation metadata, declaration-order entry, reverse unwind, single-use continuation, intentional short-circuiting, and deterministic cleanup across asynchronous and streaming execution. Registered capabilities can now opt into application ownership with ordered asynchronous startup, reverse shutdown, partial-startup rollback, bounded cleanup, deterministic state, and privacy-safe operational failures. Every registered capability now also has bounded informational availability: ordinary registrations default available, optional checks run concurrently within dedicated deadlines, safe failures normalize to unavailable, ordered fresh reports emit transition-only events, and `GET /v1/capabilities/availability` remains separate from execution and health. The Runtime Foundation milestone is complete, and the next priority is capability health reporting.

---

The capability-health reporting work described in the historical Current Focus
summary is complete. The documented capability catalog is also complete,
including embeddings, moderation, image generation, transcription, reranking,
translation, text-to-speech, video jobs, and batch inference. There is no
remaining capability implementation gap in the current roadmap. The next
potential milestone is Agent Runtime, which remains deferred until its
workflow, tool-execution, policy, and audit contracts are explicitly planned.

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

**Status:** ✅ Completed

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
- Dedicated unit-test and integration-test CI stages
- Real-process end-to-end integration test suite
- Deterministic child-process startup, readiness, output capture, and cleanup
- Dockerfile build checks in continuous integration
- Production container smoke-test automation
- Version-tagged GHCR publication workflow
- Multi-platform AMD64 and ARM64 container builds
- Container build provenance and SBOM generation
- Docker base-image dependency updates
- Deterministic Python wheel and source-distribution builds
- Distribution content and core-metadata validation
- Isolated wheel and source-distribution installation validation
- Installed dependency-consistency checks
- Installed runtime HTTP, request-correlation, and shutdown smoke tests
- Runtime version metadata derived from the installed distribution
- Wheel and source-distribution assets attached to GitHub releases
- Dedicated package build and installation CI stage
- Dedicated Kubernetes render and real-cluster smoke-test CI stage
- CodeQL Python coverage workflow on pull requests, main pushes, and weekly schedule
- Locked dependency vulnerability scanning with `pip-audit`
- Pull-request, main, and scheduled secret scanning with Gitleaks
- Release recovery procedures for version, tag, asset, and publication failures

Milestone 2 is complete: the listed automation is active, verified, and documented in the repository.

---

## Milestone 3 — Runtime Foundation

**Status:** ✅ Completed

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
- Terminal response completion distinguished from post-response disconnects
- Immutable typed timeout configuration
- Environment-configurable provider request deadlines
- Environment-configurable stream-idle deadlines
- Provider-neutral timeout enforcement
- Runtime timeout normalization without masking caller cancellation
- Production entry-point startup validation over real TCP connections
- Environment-driven runtime composition validation
- Bounded readiness polling and process-failure diagnostics
- Immutable typed graceful-shutdown configuration
- Environment-configurable active-workload drain deadline
- Production server cancellation-cleanup lifecycle
- Graceful shutdown for active non-streaming requests
- Graceful shutdown for active SSE streams
- Prompt over-deadline provider-stream finalization
- Correlated shutdown cancellation lifecycle events
- Bounded active-workload process shutdown validation
- Safe typed-configuration failure event and bounded process exit
- Runtime, provider, and observability startup configuration summaries
- Application startup and shutdown lifecycle events
- Server drain, cancellation cleanup, and terminal shutdown events
- Immutable typed dependency-readiness configuration
- Provider-neutral asynchronous dependency health contract
- OpenAI and Ollama-compatible provider metadata checks
- Optional required-model metadata validation without inference
- Stable bounded readiness failure reasons
- Runtime-owned dependency-check deadline
- Monotonic successful and failed result caching
- Concurrent single-flight readiness refresh
- Backward-compatible disabled readiness defaults
- Dependency-aware HTTP 200 and 503 readiness responses
- Dependency state-transition operational events
- Health-check client shutdown lifecycle
- Public `TrussiumError` root with stable code and safe-message attributes
- Configuration and runtime-execution exception branches
- Lifecycle and dependency exception branches
- Capability and provider exception branches
- Backward-compatible `CapabilityExecutionError` inheritance
- Backward-compatible `OpenAIProviderError` inheritance
- Top-level public exception exports
- Native cancellation, validation, framework, and SDK exception boundaries
- Exception hierarchy privacy and extension guidance
- Public asynchronous runtime-service lifecycle protocol
- Immutable ordered runtime-service lifecycle plan
- Declaration-order service startup
- Reverse-order service shutdown
- Partial-startup rollback of successfully started services
- Positive finite per-service cleanup configuration
- Environment-configurable runtime-service cleanup deadline
- Cleanup continuation across independent failures and timeouts
- Stable aggregate runtime-service lifecycle failures
- Deterministic lifecycle state-transition enforcement
- Native lifecycle cancellation preservation
- Structured service startup, rollback, shutdown, timeout, and cancellation events
- Bounded service identity, phase, outcome, code, and error-class fields
- Backward-compatible FastAPI lifespan integration
- Preserved readiness-client and tracing-exporter shutdown order
- Runtime-service lifecycle extension and privacy guidance
- Public application-scoped runtime service registry
- Explicit insertion-ordered service registration
- Stable optional and required service lookup
- Immutable ordered service-name and service-instance discovery snapshots
- Duplicate registration protection without replacement or reordering
- One-way idempotent registry sealing before lifecycle composition
- Lifecycle ownership derived from the sealed registry snapshot
- Backward-compatible ordered `runtime_services` application-factory API
- Optional preconfigured registry injection and application-state discovery
- Stable typed duplicate, missing-service, and sealed-registry errors
- Shared bounded runtime-service name validation
- Runtime-service registry composition and privacy guidance
- Public optional runtime-component health-check protocol
- Immutable bounded component health values and aggregate reports
- Healthy, degraded, unavailable, and unknown component states
- Validated service identities and stable bounded reason codes
- Sealed-registry-backed component health reporter
- Insertion-ordered component discovery and report output
- Concurrent component evaluation with deterministic aggregate precedence
- Positive finite environment-configurable per-component deadline
- Safe timeout, exception, invalid-result, and identity-mismatch normalization
- Native component-health cancellation preservation
- Serialized fresh report requests without result caching
- Transition-only structured component health events
- Informational HTTP 200 `/health/components` endpoint
- Preserved liveness, dependency readiness, and Kubernetes probe behavior
- Health, metrics, and tracing exclusion for component reporting
- Component health composition, operations, and privacy guidance

---

## Milestone 4 — Capability Framework

**Status:** ✅ Completed

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
- Canonical provider-neutral capability identities
- Immutable capability registration values
- Explicit insertion-ordered capability registration
- Stable optional and required capability lookup
- Immutable ordered capability discovery snapshots
- Duplicate registration protection
- One-way idempotent registry sealing
- Safe typed registry and contract-validation errors
- Application-owned resolved capability registry
- Registry-backed chat API dependency resolution
- Existing chat factory shortcut compatibility
- Immutable bounded capability metadata values
- Optional public version, description, and streaming declarations
- Legacy-compatible minimal name-only metadata
- Registration-bound metadata identity validation
- Immutable ordered registry metadata snapshots
- Stable optional and required metadata lookup
- Canonical `chat.completions` metadata
- Application-owned metadata composition
- Ordered `GET /v1/capabilities` external discovery
- Stable empty discovery response
- Provider, model, implementation, and configuration privacy boundary
- Sealed-registry-backed provider-neutral capability execution pipeline
- Generic non-streaming and streaming invocation callbacks
- Single canonical capability resolution per execution
- Complete asynchronous and streaming execution-context binding
- Result and event identity preservation without protocol translation
- Native normalized-error, cancellation, and unexpected-failure propagation
- Deterministic upstream stream cleanup across every terminal path
- Application-owned pipeline composition and chat JSON/SSE integration
- Public structural capability middleware contract
- Immutable resolved capability invocation metadata
- Ordered application-owned middleware snapshots
- Declaration-order middleware entry and reverse unwind
- Single-use non-streaming and streaming continuations
- Intentional result and stream short-circuiting
- Duplicate downstream execution protection
- Complete middleware execution-context propagation
- Lazy middleware and capability stream creation
- Result and event identity preservation through middleware
- Innermost-first cleanup of every created stream layer
- Primary failure preservation across cleanup failures
- Backward-compatible empty middleware composition
- Chat JSON and SSE middleware integration
- Discovery-free middleware behavior
- Public optional lifecycle-aware capability protocol
- Sealed-registry-derived immutable lifecycle plan
- Canonical registry identities for lifecycle ownership
- Registry-order capability startup
- Reverse-order capability shutdown
- Partial-startup rollback of completed hooks
- Positive finite shared per-capability cleanup deadline
- Cleanup continuation across independent failures and timeouts
- Stable aggregate capability lifecycle failures
- Deterministic lifecycle state-transition enforcement
- Native lifecycle cancellation preservation
- Structured capability startup, rollback, shutdown, timeout, and cancellation events
- Bounded capability identity, phase, outcome, code, and error-class fields
- Runtime-service and capability application lifecycle ordering
- Backward-compatible ordinary and chat capability composition
- Capability lifecycle extension and privacy guidance
- Frozen provider-neutral capability availability values and status
- Optional asynchronous capability availability protocol
- Sealed source-registry reporting in registration order
- Default availability for ordinary registered capabilities
- Concurrent fresh checks with serialized reports and dedicated deadlines
- Stable timeout and check-failure normalization
- Aggregate available and unavailable semantics
- Native availability-check cancellation preservation
- Transition-only bounded availability operational events
- Informational `GET /v1/capabilities/availability` endpoint
- OpenAPI, package, container, real-process, and Kubernetes validation
- Capability availability configuration and extension guide
- Frozen provider-neutral capability health values and statuses
- Optional asynchronous capability health protocol
- Sealed source-registry health reporting with concurrent fresh checks and stable ordering
- Unknown defaults for ordinary capabilities, safe timeout and check-failure normalization
- Aggregate unavailable, degraded, unknown, and ok semantics
- Transition-only bounded health events and informational `GET /v1/capabilities/health`
- Capability health configuration, OpenAPI, package, container, real-process, and Kubernetes validation
- Capability health extension and privacy guidance
- Provider-neutral non-streaming embeddings capability
- Immutable embeddings request, response, vector, and usage contracts
- OpenAI-compatible embeddings adapter and `POST /v1/embeddings`
- Sealed registry, execution-context, OpenAPI, and privacy-boundary integration
- Provider-neutral non-streaming moderation capability and `POST /v1/moderations`
- Informational safety classification without execution gating or policy enforcement
- Provider-neutral non-streaming image generation and `POST /v1/images/generations`
- Provider-neutral non-streaming audio transcription and `POST /v1/audio/transcriptions`
- Provider-neutral non-streaming reranking and `POST /v1/rerankings`
- Provider-neutral non-streaming translation and `POST /v1/translations`
- Provider-neutral non-streaming text-to-speech and `POST /v1/audio/speech`

The capability framework is complete. Future interfaces may extend the
provider-neutral contracts through separately reviewed changes.

---

## Milestone 5 — Provider Framework

**Status:** ✅ Completed

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
- Trussium-enforced non-streaming provider deadlines
- Per-event provider stream-idle deadlines
- Stream-idle deadline reset after every provider event
- Prompt provider iterator finalization after timeout
- Stable provider request and stream timeout error codes
- Immutable typed provider configuration
- Explicit provider selection, base URL, and credential settings
- Backwards-compatible OpenAI environment configuration
- OpenAI SDK request serialization integration coverage
- OpenAI Responses API JSON parsing integration coverage
- OpenAI Responses API streaming-event integration coverage
- Deterministic local fake OpenAI Responses API
- End-to-end upstream error normalization coverage
- Ollama self-hosted chat adapter using the compatible Responses API
- Provider-aware normalized response and stream identity
- Provider-aware SDK error codes and safe messages
- Deterministic Ollama-compatible JSON and SSE integration coverage
- Opt-in live Ollama compatibility test suite
- Live JSON and streaming validation against Ollama 0.32.5
- Model-preserving token-usage normalization for Ollama
- Provider-aware correlated Ollama lifecycle logging
- Standalone self-hosted Piper speech adapter
- Provider-neutral provider interface and immutable metadata contract
- Explicit ordered provider registry with typed lookup and sealed composition
- Ordered bounded `GET /v1/providers` provider discovery
- Provider capability reporting through immutable metadata and discovery
- Deterministic provider startup, rollback, reverse shutdown, and bounded cleanup
- Explicit allowlisted provider plugin loading with compatibility and permission checks
- Optional bounded provider model-availability discovery with runtime deadlines
- Informational provider health reporting with bounded checks and stable reasons
- Provider credential validation through opt-in dependency-aware readiness
- First additional managed provider adapter via `trussium-provider-anthropic`

### Remaining

No provider-framework deliverables are currently outstanding. Future managed
providers may be added as separately versioned adapters that implement the
provider-neutral contracts and register explicitly with the runtime.

Ollama validation demonstrates that Trussium's chat, execution, timeout,
observability, and HTTP abstractions are independent of a managed OpenAI
deployment while reusing a compatible wire protocol. Future providers should
continue to reuse the normalized capability contracts rather than introducing
provider-specific runtime paths.

---

## Milestone 6 — Chat Runtime and HTTP API

**Status:** ✅ Completed

Deliver the first complete, customer-testable Trussium runtime workflow.

### Delivered

- `POST /v1/chat/completions`
- `GET /v1/capabilities`
- Ordered provider-neutral capability metadata discovery
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
- Consistent JSON error envelopes for validation and runtime failures
- Bounded runtime model aliasing for stable client-facing model names
- Consistent non-blank validation across capability request fields
- Explicit `/v1` HTTP API versioning policy and compatibility rules
- Runnable Python client application example using the dedicated SDK
- Production-oriented API reference and operational contract
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
- Completed SSE responses remain distinct from interrupted streams
- Runtime-enforced non-streaming provider timeouts
- Provider request timeouts mapped to HTTP 504
- Runtime-enforced stream-idle timeouts
- Normalized SSE timeout error events
- Correlated provider and capability timeout failure lifecycles
- Configurable timeout defaults and environment overrides
- Real-network liveness and readiness tests
- End-to-end normalized JSON completion tests
- End-to-end normalized SSE completion tests
- End-to-end provider rate-limit mapping tests
- End-to-end request and execution correlation assertions
- End-to-end structured lifecycle ordering assertions
- Sensitive prompt and credential log-exclusion assertions
- Real-process active JSON request shutdown draining
- Real-process active SSE shutdown draining
- Listening-socket closure during active-workload shutdown
- Over-deadline SSE cancellation and upstream finalization
- Shutdown cancellation lifecycle correlation and ordering
- Bounded signal-aware production process exit assertions
- Explicit OpenAI and Ollama runtime composition
- Ollama normalized JSON completion tests
- Ollama normalized SSE completion tests
- Provider-aware response, execution-context, and lifecycle metadata
- Live self-hosted model compatibility validation

This milestone represents Trussium’s first usable vertical slice and is complete; additional model capabilities are now layered on the stable API.

---

## Milestone 7 — Routing and Resilience

**Status:** ✅ Complete

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

### Delivered

- Deterministic provider-priority routing over the sealed provider registry
- Explicit provider priority configuration with registration-order fallback
- Bounded retry policy with stable provider failure classification
- Execution-boundary retry attempts and provider request timeout enforcement
- Deterministic provider fallback for transient execution failures
- Non-streaming chat execution integration for provider fallback
- Bounded non-streaming chat model fallback within selected providers
- Bounded provider circuit breaking for repeated transient failures
- Health-aware provider candidate filtering
- Bounded routing decision metadata and structured telemetry events
- Routing decision Prometheus metrics and trace-span linkage
- Bounded non-streaming chat idempotency handling
- Explicit per-call routing retry-budget enforcement

Milestone 7 is complete. Routing is intentionally deterministic, bounded, provider-neutral, and process-local. Adaptive weighting, distributed circuit state, durable idempotency, and AI-assisted routing are deferred until operational requirements justify their added complexity.

---

## Milestone 8 — Identity, Governance, and Usage Controls

**Status:** ✅ Completed

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

### Delivered

- Opt-in bearer API-key authentication for `/v1/*` routes
- Constant-time credential comparison and generic `401` failure responses
- Public health, readiness, metrics, and API documentation endpoints for operations
- Secret-safe immutable authentication settings and deployment documentation
- Optional tenant identity propagation through request context, logs, and traces
- Optional project identity propagation through request context, logs, and traces
- Optional application identity propagation through request context, logs, and traces
- API-key bindings to trusted tenant, project, and application identities
- Bounded capability allow-lists for authenticated API-key identities
- Optional identity-aware process-local rate limiting with `429` retry guidance
- Bounded identity-scoped usage metering and normalized token accounting
- Optional process-local identity-scoped request quotas and token budget enforcement
- Provider-neutral usage exporter protocol for private and operational integrations
- Bounded privacy-safe audit events with request attribution
- Tenant-aware provider allow-lists with process-owned credential isolation

This milestone establishes open-source governance primitives. Hosted governance,
durable compliance storage, and distributed control-plane enforcement remain
outside this repository.

---

## Milestone 9 — Cloud-Native Operations

**Status:** ✅ Completed

Make Trussium deployable and operable across modern cloud-native environments.

### Delivered

- Production multi-stage Docker image
- Locked uv production dependency installation
- Non-editable package installation isolated from the source tree
- Minimal final runtime stage without build or development tools
- Dedicated numeric non-root runtime identity
- Read-only root filesystem compatibility
- Dropped-capability and no-new-privileges compatibility
- Port 9000 container contract
- OCI liveness health check
- Direct SIGTERM delivery through an exec-form entry point
- Bounded graceful container shutdown validation
- OCI source, revision, version, creation-time, and license metadata
- Deterministic image metadata and runtime smoke tests
- Multi-platform Linux AMD64 and ARM64 release builds
- Automated GitHub Container Registry publication
- Build provenance and software bill of materials generation
- Container build-context allowlisting
- Production container operations documentation
- Configurable graceful shutdown for active requests and streams
- Bounded cancelled-request resource cleanup
- Active-workload graceful shutdown operations documentation
- Maintained Kubernetes Kustomize base and production overlay
- Dedicated Namespace and token-free runtime ServiceAccount
- ConfigMap integration for non-secret runtime settings
- Optional Secret integration for provider configuration and credentials
- Private GHCR image-pull Secret integration and operations guidance
- Release-pinned production image tags updated by semantic release
- Hardened pod and container security contexts matching the OCI image
- Startup, liveness, and readiness probes on the port 9000 health contract
- CPU and memory requests and limits
- Autoscaler-managed production deployment with two-replica availability floor
- Topology spreading across cluster nodes
- Zero-unavailable rolling deployment strategy
- PodDisruptionBudget for voluntary disruption protection
- Kubernetes termination grace period aligned with active-workload draining
- Client-side Kustomize render and schema validation automation
- Real Kind-cluster deployment, replica, security, health, and correlation smoke tests
- Kubernetes customization, upgrade, rollback, scaling, and removal documentation
- Independently versioned production `trussium` Helm chart
- Schema-validated Helm values and existing Secret integration
- Real Kind-cluster Helm install, health, upgrade, rollback, and uninstall validation
- Automated Helm release packaging, GitHub release assets, and OCI publication
- App-scoped Prometheus-compatible runtime metric registry and endpoint
- Python and Linux process runtime collectors
- Bounded HTTP request counter and duration histogram labels
- Active request gauge covering complete JSON and SSE lifecycles
- Health and scrape traffic exclusion from workload metrics
- Configurable runtime metrics enablement
- Production `autoscaling/v2` HorizontalPodAutoscaler
- Named-container CPU target with bounded scale-up and stabilized scale-down
- Pinned Metrics Server Kind validation with an active live HPA
- Runtime metrics, scraping, and autoscaling operations documentation
- OpenTelemetry API, SDK, and OTLP HTTP/protobuf exporter integration
- App-scoped tracer provider, resource, parent-based sampler, processor, and exporter ownership
- Inbound W3C `traceparent` extraction without process-global provider mutation
- Complete HTTP server, capability internal, and provider client spans for JSON and SSE lifecycles
- Completed, failed, and cancelled span outcome handling
- Health, readiness, and metrics trace exclusion
- Bounded semantic and `trussium.*` span attributes without payload or credential capture
- Automatic structured-log enrichment with active trace and span identifiers
- Typed immutable trace enablement, service, sampling, endpoint, and timeout configuration
- OTLP protobuf real-process export validation against a deterministic local collector
- OpenTelemetry sampling, privacy, collector, lifecycle, and troubleshooting documentation
- Outbound W3C `traceparent` and optional `tracestate` provider propagation
- OpenAI and Ollama-compatible JSON and SSE cross-service trace continuity
- Sampled and unsampled downstream propagation without global HTTP instrumentation
- Explicit baggage, arbitrary-header, request-ID, payload, and credential propagation boundaries
- Deterministic downstream extraction and real-process OpenAI SDK propagation validation
- Stable structured operational event contract
- Bounded runtime, provider, and observability configuration summaries
- Provider configuration readiness distinguished from dependency health
- Application and server startup, stopping, and stopped lifecycle events
- Graceful-drain and cancellation-cleanup timeout events
- Background trace-export failure events
- Safe configuration failure logging without rejected values or tracebacks
- Fixed operational-field allowlist and documented privacy boundary
- Unit and real-process operational event validation
- Structured operational logging collection and troubleshooting documentation
- Independently importable Grafana runtime overview, structured-log, and trace dashboards
- Stable dashboard UIDs with selectable Prometheus, Loki, and Tempo data sources
- Runtime demand, active-work, outcome, status, latency, CPU, memory, and uptime panels
- Operational configuration, lifecycle, failure, cancellation, shutdown, and export log views
- Recent, failed, slow, HTTP, capability, and provider trace searches
- Dashboard query contracts preserving bounded metric labels and telemetry privacy
- Pinned real-Grafana provisioning and dashboard API validation in continuous integration
- Dashboard import, provisioning, collection, operator workflow, and troubleshooting documentation
- Portable Prometheus runtime alert starter profile with stable names and runbook links
- Missing-telemetry, sustained-failure, cancellation, p95-latency, and process-restart conditions
- Minimum-traffic guards preserving failure, cancellation, and low-volume semantics
- Explicit reference thresholds, hold windows, severity, tuning, routing, and maintenance guidance
- Complete metric, structured-event, dashboard, log, and trace investigation runbooks
- Privacy and cardinality boundaries for alerts and notification payloads
- Digest-pinned real-Prometheus syntax and synthetic semantic validation in continuous integration
- Operator-owned Alertmanager, Grafana Alerting, receiver, schedule, and incident-management boundaries
- Opt-in provider and required-model dependency readiness checks
- Backward-compatible local-only readiness and provider-independent liveness
- Stable authentication, permission, throttling, timeout, reachability, model, and unexpected-failure reasons
- Runtime-owned timeout, monotonic cache, and concurrent single-flight refresh semantics
- Bounded readiness configuration and state-transition operational events
- Real-process OpenAI SDK missing-model and recovery validation
- Dependency readiness privacy, rollout, and troubleshooting documentation

Health checks and structured HTTP lifecycle logs have already been delivered as part of the runtime foundation.

---

## Milestone 10 — Developer Experience and Ecosystem

**Status:** ✅ Completed

Make Trussium easy to install, integrate, extend, and operate.

### Deliverables

- Command-line interface foundation ✅
- Dedicated Python SDK repository and package ✅
- Dedicated Go SDK repository and module ✅
- Dedicated TypeScript SDK repository and package ✅
- Example applications ✅ (Python FastAPI integration example)
- Project templates ✅ (self-hosted Docker Compose starter)
- Provider development guide ✅
- Capability development guide ✅
- Plugin development kit ✅ (documentation-first boundary)
- Community provider plugin boundary ✅ (ADR-0008; explicit registration)
- Standalone provider-plugin template ✅
- First community provider plugin ✅ (`trussium-provider-vllm`)
- Managed community provider plugin ✅ (`trussium-provider-anthropic`)
- Standalone translation provider plugin ✅ (`trussium-provider-libretranslate`)
- Integration documentation ✅
- Local development environment ✅
- Runnable API usage examples ✅ (Python, Go, and TypeScript)
- SDK translation parity ✅ (Python, Go, and TypeScript)
- Self-hosted operations and troubleshooting guide ✅

SDK development should follow a stable HTTP API rather than preceding it.

The repository now includes a copyable self-hosted Docker Compose starter and
an operations guide covering local, container, Compose, and Kubernetes
deployment boundaries, health and traffic decisions, observability, upgrades,
rollback, and troubleshooting. It also includes provider and capability
development guides, an end-to-end application integration guide, a
fresh-checkout local development guide, a complete Python FastAPI example
application, and a documentation-first plugin development kit. The dedicated
SDK repositories provide runnable self-hosted examples for the three supported
languages. The community provider plugin boundary is documented in ADR-0008:
registration remains explicit and application-owned until a separately reviewed
loader provides trust, compatibility, permissions, isolation, lifecycle, and
rollback guarantees. Trusted community provider loading is now implemented as
an explicit, application-owned boundary; broader ecosystem work remains
subject to those trust, compatibility, permissions, isolation, lifecycle, and
rollback requirements.

---

## Milestone 11 — Additional AI Capabilities

**Status:** ✅ Completed

Expand the runtime after the chat execution path, routing, identity, telemetry, and deployment experience are stable.

### Delivered

- Embeddings
- Image generation
- Moderation
- Audio transcription
- Reranking
- Translation
- Video generation jobs
- Controlled tool execution
- Batch inference

Each delivered capability is a complete vertical slice: immutable contracts,
registry metadata, execution-context propagation, provider adapter, HTTP API,
error normalization, tests, and documentation. Image-generation responses expose
base64 artifacts only; audio transcription forwards multipart audio without
storing it or logging audio bytes or transcript content.

Milestone 11 is complete. Each capability was introduced as a complete vertical
slice with contracts, provider adapters, APIs, telemetry, tests, and documentation.

---

## Milestone 12 — Agent Runtime

**Status:** 🚧 In Progress (bounded workflow slice)

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

Architecture planning has started in [ADR 0044](adr/0044-agent-runtime-boundary.md).
The initial tool and invocation contract is captured in
[Agent Runtime tool and invocation contract](AGENT_RUNTIME.md).
The controlled tool foundation (`ToolRegistry`, bounded `ToolExecutor`, and
`POST /v1/tools/executions`) is delivered. The first bounded workflow
coordinator and `POST /v1/workflows/executions` are now delivered; durable
workflow state, agent state, and distributed orchestration remain deferred.
The bounded workflow lifecycle contract is documented in
[Agent Runtime workflow lifecycle](AGENT_RUNTIME_WORKFLOWS.md).
Result aggregation and error propagation are documented in
[Agent Runtime workflow results and errors](AGENT_RUNTIME_RESULTS.md).
The implementation gate is consolidated in the
[Agent Runtime implementation-readiness checklist](AGENT_RUNTIME_REVIEW.md).
The proposed bounded first workflow scope is documented in
[Agent Runtime first workflow scope](AGENT_RUNTIME_SCOPE.md).
The 1 September 2026 review accepted the bounded workflow scope, including
admission limits, timeout and caller-cancellation cleanup, normalized results,
and HTTP exposure. Workflow lifecycle events now provide bounded audit signals
without tool payloads. A storage-neutral immutable audit-record contract is now
defined, with an injectable no-op-by-default audit sink; persistence remains
deferred. Audit delivery is bounded by a finite timeout without retries.
Workflow shutdown admission and bounded draining are now implemented locally;
the application lifespan now invokes the drain before resource teardown.
Workflow metrics now expose active executions, terminal outcomes, admission
rejections, and drain outcomes with bounded labels. Cross-process coordination
remains deferred. Policy, approval, limits, and security
expansion remain separately gated.

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
- Validated Python wheels and source distributions
- Isolated installation and installed-runtime smoke tests
- Python distribution assets attached to GitHub Releases

Future release improvements should include:

- Upgrade notes for breaking changes
- Release recovery procedures
- Compatibility guarantees for public interfaces
- Independent versioning for separately released repositories

Public interface stability should be clearly documented before the first stable release.

See the [Trussium 1.0 Stability Contract](RELEASE_1_0_CONTRACT.md) for the
reviewed public compatibility boundary and change requirements.

The proposed release set and approval gates are recorded in the
[1.0.0 Release Candidate manifest](RELEASE_1_0_CANDIDATE.md).

### 1.0 release-readiness baseline

The current OSS release baseline is reviewed across the independently versioned
repositories:

- Runtime `v0.98.1` is the validated HTTP and container baseline.
- Helm chart `v0.10.0` targets runtime `v0.98.1`.
- Trussium Operator `v1.0.0` is validated against runtime `v1.0.0` and
  chart `v1.0.0`.
- SDKs and provider adapters remain separately versioned and released.
- The deferred Agent Runtime milestone is outside the first stable OSS release
  scope.

The first major release requires a reviewed breaking-change report, explicit
version decisions for each selected repository, passing repository CI, and
post-release verification of GitHub, OCI, and package artifacts. No repository
should be tagged or published until that checklist is complete.

---

## Immediate Priorities

The first post-1.0 priority is maintenance and release health:

1. Monitor dependency and vulnerability alerts across all public repositories.
2. Keep release, container, compatibility, and documentation workflows healthy.
3. Review historical compatibility proposals and track operational fixes.

Additional capability interfaces and the deferred Agent Runtime remain separate
future milestones and require their own compatibility and operational reviews.

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
- Community-contributed providers and plugins

These items are exploratory and do not represent committed deliverables.
