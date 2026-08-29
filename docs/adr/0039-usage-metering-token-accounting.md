# ADR-0039: Bounded usage metering and token accounting

## Status

Accepted

## Context

Identity and authorization controls need usage signals for future quotas and budgets, but the runtime must not retain sensitive payloads or depend on a durable billing system at this stage.

## Decision

Add a bounded process-local `UsageMeter` that aggregates request counts and provider-normalized token usage by tenant/project/application identity. Chat and embeddings record their normalized response usage; streaming records a request without assuming token metadata. The meter is exposed through application state for later export integration and stores no payloads.

## Consequences

- Operators and integrations have a low-cardinality usage signal for governance decisions.
- Token counts remain provider-neutral and use existing normalized contracts.
- Process restarts reset counters; durable export, quotas, budgets, and billing remain future work.
