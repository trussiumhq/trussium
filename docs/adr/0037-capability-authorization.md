# ADR-0037: Bounded capability authorization for API-key bindings

## Status

Accepted

## Context

API-key identity bindings establish trusted governance scope, but a credential may still need to be limited to specific runtime capabilities. The first policy should remain deterministic, local, and compatible with existing unbound credentials.

## Decision

Add an optional bounded `capabilities` allow-list to each API-key identity binding. After constant-time authentication, the middleware derives the capability from the `/v1/` path and returns a generic `403` when a non-empty allow-list does not contain it. Empty lists allow all capabilities for that binding; legacy unbound API keys remain unrestricted for backwards compatibility.

## Consequences

- Operators can apply simple capability-level least privilege without provider coupling.
- Authorization failures have a stable response and do not disclose policy details or credentials.
- Roles, dynamic policy stores, tenant/project relationship checks, quotas, and audit persistence remain future work.
