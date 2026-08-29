# Application identity propagation

Trussium accepts an optional application identifier beneath tenant and project scopes:

```http
X-Application-ID: customer-portal
```

The value is bounded to 128 characters and the characters `A-Z`, `a-z`, `0-9`, `-`, `_`, `.`, and `:`. It is carried as `ExecutionContext.application_id` and automatically appears in structured logs and HTTP trace spans. Invalid values are ignored.

Application identity is attribution metadata. Runtime authentication, authorization, process-local quotas, and token budgets may use it when an authenticated identity binding establishes the claim; durable application records and hosted governance remain separate services.
