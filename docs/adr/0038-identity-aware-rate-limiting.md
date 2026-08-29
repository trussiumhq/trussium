# ADR-0038: Bounded identity-aware rate limiting

## Status

Accepted

## Context

Authenticated runtime identities need protection from excessive request volume, but a first implementation should remain deterministic, bounded, and independent of external infrastructure.

## Decision

Add an optional process-local fixed-window middleware for `/v1/*` routes. The bucket key uses verified tenant/project/application claims when available, otherwise the client address. Limits are configured with immutable settings, disabled by default, and return a generic `429` plus `Retry-After` when exhausted.

## Consequences

- Operators can apply a simple runtime safety limit without changing providers or clients.
- Identity buckets prevent unrelated verified applications from sharing one quota.
- Counters are not shared across replicas and are not durable; distributed quotas and usage accounting remain future work.
