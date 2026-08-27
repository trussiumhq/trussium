# ADR 0016 — Stable model aliases

- Status: Accepted
- Date: 2026-08-27

## Decision

Support an application-owned, bounded model-alias map in runtime settings.
Aliases resolve exact client model names to concrete provider model IDs before
capability execution. The resolved model is used consistently in responses,
streaming events, execution context, and provider observability.

## Consequences

Operators can migrate or retarget concrete models without changing clients.
Aliases remain explicit configuration, do not perform discovery or routing,
and do not alter unmapped model names. Validation rejects ambiguous or unsafe
names before startup while preserving credential and payload privacy.
