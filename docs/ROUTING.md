# Provider-priority routing

The runtime exposes a deterministic `ProviderRouter` over the sealed provider
registry. Configure an ordered priority list through
`TRUSSIUM_ROUTING__PROVIDER_PRIORITY` (for example, `[
"anthropic", "openai"
]` in settings JSON). The first registered provider advertising the requested
provider-neutral capability is selected.

When no priority is configured, registry insertion order is used. Selection is
local and deterministic: it performs no network calls, health probes, retries,
fallback, or model inference. Those behaviors remain separate Milestone 7
features. A capability with no matching provider returns no selection so the
existing unavailable-capability handling remains in control.
