# ADR-0009: Provider Interface and Metadata Contract

**Status:** Accepted

**Date:** 2026-08-27

**Related Documents:**

- [Provider Development](../PROVIDER_DEVELOPMENT.md)
- [ADR-0008: Community Provider Plugin Boundary](0008-community-provider-plugin-boundary.md)
- [ROADMAP](../ROADMAP.md)

## Context

Built-in and independently released provider adapters currently expose
capabilities directly, but the runtime has no common provider-level identity or
metadata contract. That makes future provider registration and discovery harder
to standardize while risking leakage of provider-specific implementation data.

## Decision

Define a small runtime-checkable `Provider` protocol with immutable
`ProviderMetadata`. Metadata contains a bounded provider name, version,
provider-neutral capability identities, and an optional bounded description.
Provider implementations expose their capability adapters in stable order.
Applications continue to construct and register providers explicitly; dynamic
loading, credentials, health checks, and lifecycle management remain separate
milestones.

## Consequences

Provider adapters can publish consistent, privacy-safe identity information and
future registries can consume one stable interface. Existing capability classes
and explicit community-plugin registration remain compatible. The contract does
not itself grant network, filesystem, subprocess, or credential permissions.
