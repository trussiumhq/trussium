# API-key identity bindings

API keys may be bound to trusted tenant, project, and application claims through nested settings:

```bash
TRUSSIUM_AUTHENTICATION__IDENTITY_BINDINGS='[{"key":"replace-with-a-secret","tenant_id":"acme","project_id":"research","application_id":"portal"}]'
```

Bindings are represented as immutable `SecretStr` values. After constant-time authentication, the runtime replaces request-supplied identity headers with the claims from the matched binding. Legacy unbound API keys authenticate without identity claims; their request identity fields are cleared rather than trusted. This prevents callers from self-asserting governance scope.

Identity bindings are process-local configuration. Use a deployment secret mechanism, rotate keys operationally, and add authorization policy before treating claims as permission grants.
