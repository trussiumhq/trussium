# Moderation capability

Trussium exposes provider-neutral, non-streaming text moderation at `POST /v1/moderations`.

```json
{"model":"omni-moderation-latest","input":["text to classify"]}
```

The response preserves the configured provider, requested model, per-input flagged state, categories, and scores. The endpoint is informational: it never blocks or gates chat or embeddings. Request text, credentials, endpoints, and provider-specific unbounded data remain outside structured logs and public discovery.

Automatic enforcement, filtering, policy decisions, storage, routing, retries, and agent workflows are separate concerns.
