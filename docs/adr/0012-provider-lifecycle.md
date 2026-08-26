# ADR-0012: Deterministic Provider Lifecycle

**Status:** Accepted

**Date:** 2026-08-27

**Related Documents:**

- [Provider Lifecycle](../PROVIDER_LIFECYCLE.md)
- [ADR-0010: Explicit Provider Registry](0010-provider-registry.md)
- [ADR-0005: Runtime Bootstrap Architecture](0005-runtime-bootstrap-architecture.md)

## Decision

Lifecycle-aware providers implement `ProviderService` and are coordinated by
`ProviderLifecycle`, which reuses the established runtime lifecycle semantics.
Startup follows registration order; failed partial startup rolls back completed
providers; successful shutdown runs in reverse order with bounded cleanup.

Provider lifecycle composition remains explicit and application-owned. The
metadata-only `Provider` contract remains compatible with providers that do not
own resources or need lifecycle hooks.

## Consequences

Provider-owned resources are initialized and released predictably without
duplicating lifecycle state machines or weakening cancellation behavior. Future
provider health and dynamic loading must consume the lifecycle boundary without
merging those concerns into startup.
