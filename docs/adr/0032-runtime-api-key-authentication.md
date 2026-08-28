# ADR-0032: Opt-in runtime API-key authentication

## Status

Accepted

## Context

The runtime needs a small, provider-neutral authentication boundary before tenant and project governance can be added. Existing deployments must continue to work without a credential, while protected API traffic needs a stable failure contract that does not disclose secrets.

## Decision

Add pure ASGI middleware with an immutable, bounded list of configured bearer API keys. Authentication is enabled only when at least one key is configured. It protects `/v1/*` routes, uses constant-time comparisons, and returns a generic `401` response with `WWW-Authenticate: Bearer`. Health, readiness, metrics, and API documentation paths remain public. Keys are supplied through nested settings and represented as `SecretStr` values.

This deliberately does not implement tenant identity, authorization, key rotation, quotas, or distributed identity state; those remain separate Milestone 8 deliverables.

## Consequences

- Operators can enable a minimal runtime authentication boundary without changing providers.
- Existing unauthenticated development and local deployments remain compatible.
- API keys must be delivered and rotated by deployment infrastructure.
- Multi-tenant policy and durable identity controls still require follow-up work.
