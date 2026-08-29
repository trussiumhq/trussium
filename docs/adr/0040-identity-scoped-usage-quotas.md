# ADR 0040: Identity-scoped usage quotas

## Status

Accepted

## Decision

Add optional request and normalized-token quotas to the process-local `UsageMeter`, keyed by the existing tenant, project, and application execution identity. Enforce request budgets before API execution with pure ASGI middleware and enforce token budgets when normalized provider usage is recorded.

## Rationale

This provides a safe first governance boundary without retaining prompts or responses or introducing a distributed state dependency. Zero-valued limits preserve the existing unlimited behavior.

## Consequences

Quotas reset on process restart and are independent on each replica. Distributed enforcement, billing precision, and durable usage export remain follow-up work.
