# Provider retries

Trussium now provides a bounded `RetryPolicy` and stable provider failure classification for execution layers. Retry decisions use a one-based attempt number, an explicit maximum-attempt budget, and capped exponential backoff. The runtime defaults to one attempt for backward-compatible behavior; configure `TRUSSIUM_RETRIES__MAX_ATTEMPTS` above one to enable retries.

Only rate limits, timeouts, connection failures, and normalized upstream failures are retryable by default. Invalid requests, quota exhaustion, authentication, permission failures, and cancellations are never retried. The execution coordinator applies the policy to non-streaming calls and enforces the provider request timeout. Streaming calls remain single-attempt so already-emitted events are never duplicated; provider fallback and circuit breaking remain later milestones.
