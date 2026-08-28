# Routing decision telemetry

Provider fallback emits bounded structured `provider.routing.decision` events and exposes immutable `RoutingDecision` values to an optional decision handler. Events include capability, provider, attempt, outcome, and transient failure class when applicable. No request payloads, credentials, or SDK exception text are included.
