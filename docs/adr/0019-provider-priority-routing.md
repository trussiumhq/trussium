# ADR 0019 — Deterministic provider-priority routing

- Status: Accepted
- Date: 2026-08-27

## Decision

Select providers through an application-owned ordered priority list over the
sealed `ProviderRegistry`. The first provider advertising the requested
provider-neutral capability wins; absent a priority list, registration order
is the default.

## Consequences

Routing is predictable and testable before retries, fallback, circuit breaking,
or health-aware policies are introduced. Selection performs no network I/O and
does not change provider metadata or capability execution contracts.
