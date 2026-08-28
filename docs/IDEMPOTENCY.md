# Non-streaming chat idempotency

Send an `Idempotency-Key` header with a non-streaming chat request to replay a successful response safely across client retries. The runtime stores a bounded, process-local request fingerprint and result for the configured TTL. Reusing a key with a different payload returns HTTP 409; failed requests are not cached. Streaming requests are not idempotency-cached.
