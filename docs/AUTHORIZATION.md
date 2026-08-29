# Capability authorization

An API-key identity binding may restrict access to named runtime capabilities:

```bash
TRUSSIUM_AUTHENTICATION__IDENTITY_BINDINGS='[{"key":"replace-with-a-secret","tenant_id":"acme","capabilities":["chat","embeddings"]}]'
```

Capability names are derived from the first path segment after `/v1/` (for example, `/v1/chat/completions` uses `chat`). A non-empty `capabilities` list denies requests outside that list with a generic `403` response. An empty list means the authenticated binding is not capability-restricted. Unbound legacy keys remain compatible and are not subject to binding policies.

This is a bounded allow-list, not a role hierarchy or external policy engine. It does not validate tenant/project relationships or provide quotas, budgets, or audit persistence.
