# ADR-0010: Explicit Provider Registry

**Status:** Accepted

**Date:** 2026-08-27

**Related Documents:**

- [Provider Development](../PROVIDER_DEVELOPMENT.md)
- [ADR-0009: Provider Interface and Metadata Contract](0009-provider-interface-and-metadata.md)
- [ADR-0008: Community Provider Plugin Boundary](0008-community-provider-plugin-boundary.md)

## Decision

Use an application-owned `ProviderRegistry` to compose providers explicitly.
The registry preserves insertion order, rejects duplicate metadata identities,
provides stable lookup and immutable snapshots, and seals before runtime
startup. Missing, duplicate, contract-mismatch, and post-seal mutations expose
typed bounded configuration errors.

The registry does not scan packages, import configuration-supplied names, or
grant provider permissions. Dynamic loading and provider lifecycle integration
remain separate milestones.

## Consequences

Built-in and independently released adapters have one predictable composition
boundary, while operators retain control over which code is loaded. Providers
must be constructed before sealing and future lifecycle work must consume the
sealed snapshot rather than mutating it.
