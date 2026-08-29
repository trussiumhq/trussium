# Audit events

The runtime retains a bounded, process-local `AuditTrail` for `/v1/*` request attribution. Each immutable `AuditEvent` contains request and execution IDs, optional tenant/project/application identity, method, path, status, outcome, and timestamp. Prompts, responses, credentials, and arbitrary headers are never stored.

The trail is an operational extension point, not a compliance database. Events reset on restart and are bounded with oldest-first eviction. Durable retention, compliance workflows, and commercial audit services remain private integrations.
