# Provider-priority routing

The runtime exposes a deterministic `ProviderRouter` over the sealed provider
registry. Configure an ordered priority list through
`TRUSSIUM_ROUTING__PROVIDER_PRIORITY` (for example, `[
"anthropic", "openai"
]` in settings JSON). The first registered provider advertising the requested
provider-neutral capability is selected.

When no priority is configured, registry insertion order is used. Selection is
local and deterministic: it performs no network calls, health probes, retries,
or model inference. `execute_with_fallback` can run an operation against ordered
candidates and move to the next provider only for transient failures. Circuit
breaking and model fallback remain separate Milestone 7 features. A capability
with no matching provider returns no selection so existing unavailable-capability
handling remains in control.
