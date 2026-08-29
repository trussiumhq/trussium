# Runtime rate limiting

Trussium supports an optional process-local fixed-window request limit for `/v1/*` routes:

```bash
TRUSSIUM_RATE_LIMIT__REQUESTS_PER_WINDOW=120
TRUSSIUM_RATE_LIMIT__WINDOW_SECONDS=60
```

When enabled, requests are bucketed by verified tenant/project/application identity. Requests without verified identity use the client address bucket. Exceeding the limit returns `429` with a generic error and `Retry-After` seconds. Set `requests_per_window` to `0` to disable the limiter.

Counters are in-memory and local to one runtime process. Use an ingress or distributed limiter when multiple replicas require a shared quota. This control is separate from usage metering, tenant quotas, and billing.
