# ADR 0042: Bounded audit events

## Status

Accepted

## Decision

Record a bounded, payload-free audit event for each versioned API request using the active execution context. Keep the default trail process-local and expose immutable snapshots for operational integrations.

## Rationale

Request attribution is useful for governance and troubleshooting, but retaining prompts, responses, or credentials would violate the runtime privacy boundary. A bounded local trail provides a safe baseline without requiring a commercial or distributed service.

## Consequences

Events reset on restart and are evicted oldest-first at capacity. Durable, distributed, and compliance-grade retention remains outside the open-source runtime.
