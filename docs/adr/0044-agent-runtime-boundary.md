# ADR 0044: Agent Runtime boundary and controlled execution

## Status

Proposed

## Context

Trussium’s capability and provider foundations are production-ready, but the
project does not yet define how multi-step agent workflows should be composed.
Agent execution introduces tool invocation, workflow state, policy decisions,
human approval, cancellation, limits, and audit requirements that must not be
implicit in ordinary model capability calls.

## Decision

Keep the Agent Runtime in the `trussium` repository as an opt-in runtime layer
above capabilities and providers. The first implementation must define typed,
immutable tool contracts; bounded workflow and agent lifecycles; inherited
execution context; cooperative cancellation and execution limits; explicit
policy and approval extension points; and privacy-safe audit events.

Tool execution must be explicitly registered and authorized. The runtime must
not provide unrestricted code execution, implicit network access, or hidden
credential propagation. MCP integration may be added as an adapter over these
contracts, not as a second execution path.

## Consequences

Existing capability and provider APIs remain unchanged. Agent workflows can
reuse execution correlation, lifecycle, error, tracing, and audit contracts.
The initial design requires additional state and policy boundaries, and agent
features remain opt-in until deterministic limits, cancellation, and audit
behavior are validated. The initial tool and invocation contract is documented
in [Agent Runtime tool and invocation contract](../AGENT_RUNTIME.md).

## Alternatives Considered

- **Separate repository immediately:** rejected because the first runtime layer
  directly composes existing execution and lifecycle primitives.
- **Embed agent behavior in chat capability:** rejected because it would blur
  capability contracts and make policy and audit boundaries implicit.
- **Unrestricted plugin execution:** rejected because it cannot provide a safe,
  bounded default for credentials, network access, or resource consumption.
