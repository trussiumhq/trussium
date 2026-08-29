# Project identity propagation

Trussium accepts an optional project identifier beneath a tenant boundary:

```http
X-Project-ID: research
```

The value is bounded to 128 characters and the characters `A-Z`, `a-z`, `0-9`, `-`, `_`, `.`, and `:`. It is carried as `ExecutionContext.project_id` and automatically appears in structured logs and HTTP trace spans. Invalid values are ignored.

Project identity is attribution metadata only. It does not yet enforce project permissions, quotas, budgets, or persistence, and should be trusted for governance only after an authenticated authorization layer validates the tenant/project relationship.
