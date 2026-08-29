# Usage metering and token accounting

The runtime keeps bounded, process-local aggregates for successful chat and embeddings requests. Aggregates are keyed by the active tenant/project/application identity scope (or `-:-:-` when no identity is available) and include request count, input tokens, output tokens, and total tokens.

The meter is available to application integrations as `app.state.usage_meter` and deliberately stores no prompts, responses, credentials, or request bodies. Streaming requests increment request counts but have zero token fields because provider-neutral streaming usage is not guaranteed.

Counters are in-memory and reset on process restart. Export, durable retention, quotas, and billing remain separate governance features.
