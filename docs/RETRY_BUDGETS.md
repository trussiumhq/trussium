# Routing retry budgets

Provider routing enforces a finite per-call retry budget with `TRUSSIUM_ROUTING__RETRY_BUDGET` (default `10`). The budget counts transient provider failures across fallback attempts and prevents unbounded multiplication of provider/model retries. Per-operation retry limits and circuit breakers still apply independently.
