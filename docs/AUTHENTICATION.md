# Runtime API authentication

Trussium supports optional bearer API-key authentication for application routes.

Set one or more keys through the nested settings environment variable:

```bash
TRUSSIUM_AUTHENTICATION__API_KEYS='["replace-with-a-long-random-key"]'
```

Prerequisites: a secret manager or deployment-secret mechanism, TLS at the
ingress or service boundary, and a planned rotation window. Do not commit this
value, place it in a checked-in `.env` file, or pass it as a literal in shell
history. Prefer a platform-injected environment variable or mounted secret.

Clients send the selected key as:

```http
Authorization: Bearer replace-with-a-long-random-key
```

When no keys are configured, authentication is disabled for backwards compatibility. When keys are configured, `/v1/*` routes require a valid key. `/health/live`, `/health/ready`, `/health/components`, `/metrics`, and the API documentation endpoints remain unauthenticated so probes and operators can determine service availability. Invalid credentials return `401` with `WWW-Authenticate: Bearer`; credentials are never included in responses or logs.

This is an application-boundary control, not tenant authorization or a replacement for a secret manager, ingress policy, or TLS. Keys are process-local configuration and should be supplied through a deployment secret mechanism.

## Rotation and recovery

To rotate a key, add the replacement key to the secret, deploy the updated
secret, and restart or roll the runtime so the process reloads its settings.
Verify an authenticated `/v1/` request with the new key, then remove the old
key in a second deployment. If authentication is accidentally misconfigured,
restore the last known-good secret and roll back the deployment; do not disable
TLS or expose health endpoints publicly as a recovery shortcut.
