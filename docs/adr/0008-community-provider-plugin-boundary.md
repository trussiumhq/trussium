# ADR-0008: Community Provider Plugin Boundary

**Status:** Accepted

**Date:** 2026-08-26

**Related Documents:**

- [ADR-0004: Plugin Architecture](0004-plugin-architecture.md)
- [Plugin Development Kit](../PLUGIN_DEVELOPMENT.md)
- [Provider Development](../PROVIDER_DEVELOPMENT.md)
- [ROADMAP](../ROADMAP.md)

**Supersedes:** ADR-0004 discovery and loading sections

## Context

Trussium needs a safe contribution path for community provider adapters, while
the runtime process handles credentials, network access, request deadlines,
streaming cleanup, lifecycle, and operational telemetry. Loading arbitrary
third-party packages from configuration would make installation equivalent to
executing unreviewed code and could bypass those boundaries.

## Decision

Community provider plugins use explicit, application-owned registration today.
An application imports a reviewed plugin, constructs it with explicitly granted
settings and clients, and registers its provider-neutral capability before the
sealed runtime registry is composed. The runtime does not scan packages,
execute entry points, or import names supplied by configuration.

Any future loader must be introduced by a separate implementation change after
it satisfies all of these requirements:

- signed or otherwise verifiable package provenance and an operator allowlist;
- declared and checked Trussium API compatibility;
- bounded provider-neutral metadata and duplicate-identity rejection;
- explicit permissions for network, filesystem, subprocess, and credentials;
- isolation and resource limits appropriate to the deployment boundary;
- deterministic startup, rollback, shutdown, cancellation, and failure policy;
- privacy-safe audit events without prompts, responses, secrets, or raw errors.

The loader must remain separate from plugin implementations and must fail closed
before serving traffic when validation or policy checks fail.

## Consequences

Trusted community adapters can be developed and distributed independently
without changing the core runtime, but operators must currently compose them
explicitly. Automatic discovery, package entry points, and configuration-driven
imports remain deferred until the requirements above have a tested design.

## Alternatives Considered

### Automatic package discovery now

Rejected because it would create an implicit code-execution and permission
boundary before trust, isolation, compatibility, and rollback contracts exist.

### Keep all providers in the runtime repository

Rejected because it increases coupling and prevents independent community
release and review cycles.
