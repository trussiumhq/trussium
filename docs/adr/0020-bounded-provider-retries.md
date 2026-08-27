# ADR-0020: Bounded provider retry decisions

## Status

Accepted

## Decision

Provide a provider-neutral, immutable retry policy that classifies failures into stable categories and returns capped exponential-backoff decisions. Retry budgets are explicit and finite; non-transient failures are never retried.

## Consequences

Execution coordinators can share safe retry semantics without coupling to SDK exception types. Sleeping, provider fallback, circuit breaking, and health-aware selection remain separate concerns.
