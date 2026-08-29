# Tenant identity propagation

Trussium can carry an optional tenant identifier through each HTTP request and its asynchronous capability execution context.

Clients may send:

```http
X-Tenant-ID: acme-prod
```

Tenant identifiers are limited to 128 characters and the characters `A-Z`, `a-z`, `0-9`, `-`, `_`, `.`, and `:`. Invalid or blank values are ignored rather than treated as authenticated identity. When present, the identifier is available through `ExecutionContext.tenant_id` and is automatically included in structured logs and active HTTP trace spans.

Tenant identity is attribution metadata until an authenticated identity binding establishes it. The runtime provides bounded capability authorization, local rate limits, quotas, audit snapshots, provider allow-lists, and usage exports, but does not persist tenant records or provide a hosted control plane. Treat untrusted headers as metadata only.
