# Provider discovery

Trussium exposes bounded metadata for explicitly configured providers through
`GET /v1/providers`. The endpoint reads the sealed `ProviderRegistry` snapshot
and never executes providers or performs network probes.

Each entry contains the provider name, version, supported provider-neutral
capability identities, and optional description. Credentials, URLs, models,
implementations, health, availability, prompts, responses, and provider payloads
are intentionally excluded.

The `capabilities` array is the provider capability report. It is an immutable,
declaration-time view of the capability identities the adapter registers; an
entry means the provider advertises that contract, not that an upstream service
is currently reachable. Use `GET /v1/providers/health` for bounded informational
health checks and `GET /v1/capabilities/availability` for runtime capability
availability. Those probes remain separate from discovery and never alter
provider registration.

Provider registration remains application-owned. Operators construct providers,
register them before application startup, and the application seals the registry
before serving traffic. Package scanning and configuration-driven imports remain
out of scope.
