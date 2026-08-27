# Provider health

`GET /v1/providers/health` provides an informational, ordered health view for
registered providers. Providers opt into the `ProviderHealthCheck` protocol;
providers without a check are reported as `unknown`. Checks run concurrently
with a bounded deadline and never execute inference or expose credentials,
endpoints, models, or payloads. The endpoint does not alter liveness,
readiness, routing, retries, or execution.
