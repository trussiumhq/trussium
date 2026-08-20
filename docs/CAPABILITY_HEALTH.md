# Capability Health Reporting

Trussium provides an informational, provider-neutral health view for registered
capabilities. It is separate from availability: availability says whether a
capability can currently accept work, while health can express an operational
condition without changing execution or Kubernetes traffic decisions.

## Contract

A capability may opt in with an asynchronous `check_health()` method returning
frozen `CapabilityHealth` with its exact canonical name, one of `ok`,
`degraded`, `unavailable`, or `unknown`, and a stable bounded reason for every
non-`ok` state. Ordinary registrations remain valid and report `unknown` with
`capability_health_not_reported`.

Checks run concurrently from the sealed source registry, preserve registration
order, serialize concurrent reports, and always perform a fresh evaluation.
Aggregate precedence is `unavailable`, `degraded`, `unknown`, then `ok`; an
empty registry is `ok`.

## Bounded failures and configuration

Every active check has an independent finite positive deadline, defaulting to
one second:

```bash
export TRUSSIUM_RUNTIME__CAPABILITY_HEALTH_TIMEOUT_SECONDS=0.5
```

Timeouts, raised failures, invalid values, and mismatched identities normalize
to `unavailable` with `capability_health_timeout` or
`capability_health_check_failed`. Native cancellation propagates unchanged.
Exception messages, endpoints, credentials, request data, and payloads are
never exposed.

## HTTP and operational behavior

`GET /v1/capabilities/health` always returns HTTP 200 and appears in OpenAPI.
It uses normal request correlation, structured logging, metrics, and tracing,
but is not a liveness, readiness, startup, or execution gate. State changes
emit bounded `capability.health.*` events; identical repeated reports do not.

## Boundaries

Health reporting does not alter availability, execute capability work, select
providers or models, route, retry, fall back, recover, enforce capacity or
quotas, discover plugins, add Kubernetes probes or resources, or configure the
Trussium Operator.
