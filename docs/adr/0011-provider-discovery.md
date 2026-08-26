# ADR-0011: Bounded Provider Discovery

**Status:** Accepted

**Date:** 2026-08-27

**Related Documents:**

- [Provider Discovery](../PROVIDER_DISCOVERY.md)
- [ADR-0010: Explicit Provider Registry](0010-provider-registry.md)
- [ADR-0009: Provider Interface and Metadata Contract](0009-provider-interface-and-metadata.md)

## Decision

Expose an informational `GET /v1/providers` endpoint backed by the sealed
`ProviderRegistry`. It returns provider metadata and provider-neutral capability
identities in explicit registration order. The response is bounded and excludes
credentials, endpoints, models, implementations, health, availability, and
provider payloads.

The endpoint performs no provider execution, metadata probing, or network I/O.
Provider construction and registration remain application-owned.

## Consequences

Operators and clients can inspect configured provider identities without gaining
access to sensitive configuration or triggering upstream requests. Future
provider health, model discovery, and dynamic loading must remain separate
contracts.
