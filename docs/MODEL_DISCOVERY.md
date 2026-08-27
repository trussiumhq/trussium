# Provider model discovery

Providers may implement the optional `ProviderModelDiscovery` contract to
publish bounded model metadata through
`GET /v1/providers/{provider}/models`. The endpoint performs metadata discovery
only; it never executes inference.

The runtime applies its own one-second default discovery deadline, configurable
with `TRUSSIUM_RUNTIME__MODEL_DISCOVERY_TIMEOUT_SECONDS`. Unsupported providers,
timeouts, malformed results, and provider failures return safe unavailable
reasons without raw exception text.

Model identifiers and ownership values are bounded and validated. Credentials,
endpoints, prompts, responses, provider payloads, and implementation details
are excluded from the response.
