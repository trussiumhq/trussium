# Provider discovery

Trussium exposes bounded metadata for explicitly configured providers through
`GET /v1/providers`. The endpoint reads the sealed `ProviderRegistry` snapshot
and never executes providers or performs network probes.

Each entry contains the provider name, version, supported provider-neutral
capability identities, and optional description. Credentials, URLs, models,
implementations, health, availability, prompts, responses, and provider payloads
are intentionally excluded.

Provider registration remains application-owned. Operators construct providers,
register them before application startup, and the application seals the registry
before serving traffic. Package scanning and configuration-driven imports remain
out of scope.
