# Usage exports

The runtime exposes the provider-neutral `UsageExporter` protocol for integrations that need bounded usage snapshots. Pass an exporter to `UsageMeter(exporter=...)`; its `export(snapshot)` method receives an immutable mapping keyed by the existing identity bucket.

Exporters are optional and process-local. Export failures are intentionally isolated from request execution, and snapshots contain counters only—not prompts, responses, credentials, billing rules, or hosted-service dependencies. Commercial billing and distributed collection can implement this protocol in a separate private integration.
