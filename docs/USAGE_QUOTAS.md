# Usage quotas

Trussium supports optional process-local quotas per active tenant/project/application identity.
Configure `TRUSSIUM_QUOTA__REQUESTS` and `TRUSSIUM_QUOTA__TOKENS` with positive limits; `0` disables that limit. Requests that exceed a request limit are rejected before provider execution with HTTP `429` and `usage_quota_exceeded`. Token limits use normalized provider-reported usage and reject a completion that would exceed the configured budget.

Quotas are intentionally bounded and in-memory. They reset on restart and are not a replacement for distributed billing or shared multi-replica enforcement; use a future usage-export integration for those deployments.
