# ADR-0036: Bind API keys to trusted runtime identities

## Status

Accepted

## Context

Tenant, project, and application identifiers can be supplied as request metadata, but those headers are untrusted. API-key authentication needs a deterministic way to associate a credential with governance scope before authorization is introduced.

## Decision

Add bounded immutable API-key identity bindings to authentication settings. A binding contains a `SecretStr` key and optional validated tenant, project, and application identifiers. The authentication middleware performs constant-time matching, clears request-derived identity claims, then installs only the matched binding claims in the execution context for the duration of the request. Existing unbound API keys remain supported but carry no identity claims.

## Consequences

- Authenticated requests receive trusted attribution without changing provider adapters.
- Callers cannot self-assign tenant, project, or application scope with headers.
- Credential rotation and authorization policy remain deployment/application responsibilities.
