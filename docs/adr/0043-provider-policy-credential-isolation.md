# ADR 0043: Provider policy and credential isolation

## Status

Accepted

## Decision

Allow authenticated identity bindings to carry a bounded provider allow-list. Apply it in the provider router before selection and fallback, while keeping provider credentials exclusively in process-owned immutable settings.

## Rationale

Tenant-aware routing needs a provider boundary, but identities must not be able to inject or retrieve credentials. This provides a safe local policy primitive without introducing a hosted control plane.

## Consequences

An empty allow-list preserves existing routing. A non-empty list excludes all other providers. Credential rotation and centralized policy distribution remain deployment or private-integration concerns.
