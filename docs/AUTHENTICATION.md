# Runtime API authentication

Trussium supports optional bearer API-key authentication for application routes.

Set one or more keys through the nested settings environment variable:

```bash
TRUSSIUM_AUTHENTICATION__API_KEYS='["replace-with-a-long-random-key"]'
```

Clients send the selected key as:

```http
Authorization: Bearer replace-with-a-long-random-key
```

When no keys are configured, authentication is disabled for backwards compatibility. When keys are configured, `/v1/*` routes require a valid key. `/health`, `/ready`, `/metrics`, and the API documentation endpoints remain unauthenticated so probes and operators can determine service availability. Invalid credentials return `401` with `WWW-Authenticate: Bearer`; credentials are never included in responses or logs.

This is an application-boundary control, not tenant authorization or a replacement for a secret manager, ingress policy, or TLS. Keys are process-local configuration and should be supplied through a deployment secret mechanism.
