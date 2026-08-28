# Tenant identity propagation

Trussium can carry an optional tenant identifier through each HTTP request and its asynchronous capability execution context.

Clients may send:

```http
X-Tenant-ID: acme-prod
```

Tenant identifiers are limited to 128 characters and the characters `A-Z`, `a-z`, `0-9`, `-`, `_`, `.`, and `:`. Invalid or blank values are ignored rather than treated as authenticated identity. When present, the identifier is available through `ExecutionContext.tenant_id` and is automatically included in structured logs and active HTTP trace spans.

This feature provides attribution only. It does not grant permissions, enforce isolation, calculate quotas, or persist tenant records. Those controls remain separate Milestone 8 work. Treat the header as untrusted unless an upstream authentication and authorization layer has established its value.
