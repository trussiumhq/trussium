# ADR 0014 — Informational provider health reporting

- Status: Accepted
- Date: 2026-08-27

## Decision

Expose provider health through an optional asynchronous provider check and the
informational `GET /v1/providers/health` endpoint. Reports are bounded,
ordered, deadline-limited, and application-owned. Missing checks produce
`unknown`; failures normalize to stable reasons. Health never gates execution
or Kubernetes probes.

## Consequences

Provider adapters can report operational state without coupling health to
inference. Operators must continue to define routing, readiness, credentials,
and recovery policy.
