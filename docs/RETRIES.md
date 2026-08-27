# Provider retries

Trussium now provides a bounded `RetryPolicy` and stable provider failure classification for execution layers. Retry decisions use a one-based attempt number, an explicit maximum-attempt budget, and capped exponential backoff.

Only rate limits, timeouts, connection failures, and normalized upstream failures are retryable by default. Invalid requests, quota exhaustion, authentication, permission failures, and cancellations are never retried. The policy is deterministic and does not yet perform provider fallback or sleep; those behaviors belong to the execution coordinator and later routing milestones.
