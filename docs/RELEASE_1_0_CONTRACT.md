# Trussium 1.0 Stability Contract

This document defines the public compatibility boundary for the first stable
Trussium OSS release. It is reviewed as part of the change-management process
for release issue [#307](https://github.com/trussiumhq/trussium/issues/307).

## Stable runtime boundary

- The versioned integration surface is the `/v1` HTTP API.
- JSON response envelopes, Server-Sent Events, typed error details, health
  endpoints, and `X-Request-ID` correlation are public contracts.
- Additive fields and endpoints are compatible when they preserve existing
  semantics and privacy guarantees.
- Breaking HTTP behavior requires a new major API path or a major runtime
  release with documented migration guidance.

## Deployment and package boundary

- Runtime container images and Python distributions are immutable, semantically
  versioned artifacts.
- The Helm chart and operator remain independently versioned repositories; each
  release documents the runtime versions it validates.
- SDKs and provider adapters consume the public HTTP/provider contracts and may
  release independently.

## Change requirements

Before a breaking change is accepted, its proposal must include affected
contracts, migration guidance, compatibility tests, rollback steps, and release
notes. Undocumented breaking changes are not permitted in the stable line.

The runtime release configuration permits a reviewed breaking change to advance
the 0.x line to `1.0.0`; this setting does not publish or tag a release by
itself.

The Agent Runtime milestone is deferred and is not part of this contract.
