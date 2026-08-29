# ADR 0041: Provider-neutral usage exports

## Status

Accepted

## Decision

Expose a small `UsageExporter` protocol that receives immutable, bounded counter snapshots from `UsageMeter`. Keep the protocol free of billing, persistence, transport, and provider-specific concerns.

## Rationale

Open-source deployments need an extension point for operational collection while commercial deployments may supply private exporters. Isolating exporter failures prevents optional integrations from changing request behavior.

## Consequences

The default runtime remains in-memory and has no external dependency. Export delivery, retries, durability, distributed aggregation, and billing semantics are integration responsibilities.
