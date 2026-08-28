# Health-aware routing

Provider fallback now refreshes the existing bounded provider health report before selecting candidates. Providers reported `unavailable` are excluded; healthy, degraded, and unknown providers retain deterministic priority order. Health checks remain informational and are bounded by the provider health timeout.
