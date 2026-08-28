# Chat model fallback

Configure ordered model candidates with `TRUSSIUM_ROUTING__MODEL_FALLBACKS`. A policy maps the requested model name to a bounded tuple of model IDs. Non-streaming chat tries candidates in order within the selected provider and advances only for transient failures. Without a policy, the requested model is used once. Streaming remains single-model to avoid duplicate events.
