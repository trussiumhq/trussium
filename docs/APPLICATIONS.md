# Application identity propagation

Trussium accepts an optional application identifier beneath tenant and project scopes:

```http
X-Application-ID: customer-portal
```

The value is bounded to 128 characters and the characters `A-Z`, `a-z`, `0-9`, `-`, `_`, `.`, and `:`. It is carried as `ExecutionContext.application_id` and automatically appears in structured logs and HTTP trace spans. Invalid values are ignored.

Application identity is attribution metadata only. It does not yet enforce credentials, permissions, quotas, budgets, or persistence. Those controls remain separate Milestone 8 work.
