# ADR-0026: Exclude unavailable providers during routing

## Status

Accepted

## Decision

Provider fallback consults the existing health reporter and excludes only providers with an `unavailable` status. Other statuses remain eligible in deterministic priority order.

## Consequences

Routing avoids known-unavailable providers without conflating health with liveness or readiness. Distributed health caches and adaptive weighting remain future work.
