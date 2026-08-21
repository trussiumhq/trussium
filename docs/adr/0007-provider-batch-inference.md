# ADR-0007: Provider Batch Inference

**Status:** Accepted

**Date:** 2026-08-21

## Context

Batch providers process asynchronous work from provider-managed input files.
Mirroring those files or their results in Trussium would create a second durable
data store, expand the privacy boundary, and make lifecycle ownership unclear.

## Decision

Trussium will expose a provider-neutral batch-job lifecycle for a constrained
set of provider-supported endpoints. The initial implementation creates,
retrieves, and cancels jobs using a caller-owned provider input-file reference.
It returns normalized job metadata only; input and output files remain owned by
the provider and are not downloaded, persisted, or logged by Trussium.

The initial contract permits only the OpenAI chat-completions endpoint and a
fixed completion window. It does not proxy arbitrary endpoints, accept file
uploads, or expose result downloads. Provider adapters map native status and
file identifiers into immutable public contracts and propagate trace context.

## Consequences

- Applications retain control over provider-file creation and data retention.
- Trussium has no durable batch payload or result-storage responsibility.
- Batch support is intentionally limited until each additional endpoint has a
  provider-neutral contract and appropriate privacy review.

## Alternatives Considered

- **Trussium-managed uploads and result storage:** rejected because it adds a
  durable sensitive-data boundary and lifecycle that the runtime does not yet
  operate.
- **Arbitrary provider endpoint proxy:** rejected because it bypasses
  capability contracts and predictable validation.
- **Local job scheduler:** rejected because provider-managed batch jobs already
  supply the asynchronous execution lifecycle for this initial scope.
