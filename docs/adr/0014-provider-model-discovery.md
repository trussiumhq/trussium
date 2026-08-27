# ADR-0014: Bounded Provider Model Discovery

**Status:** Accepted

**Date:** 2026-08-27

**Related Documents:**

- [Provider Model Discovery](../MODEL_DISCOVERY.md)
- [ADR-0011: Bounded Provider Discovery](0011-provider-discovery.md)
- [ADR-0010: Explicit Provider Registry](0010-provider-registry.md)

## Decision

Providers may opt into `ProviderModelDiscovery`, returning validated immutable
`ProviderModel` values. Trussium exposes those values through
`GET /v1/providers/{provider}/models` with a runtime-owned deadline and stable
unavailable reasons for unsupported, timeout, malformed, and failed discovery.

The endpoint is informational and never executes inference. Provider identity,
model identifiers, and optional ownership are public bounded metadata; secrets,
endpoints, payloads, and implementation details remain private.

## Consequences

Applications can inspect provider model availability without coupling to native
SDK response types. Providers without model listing remain compatible, while
health gating, routing, aliases, and automatic model selection remain separate
features.
