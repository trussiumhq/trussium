# ADR-0006: Controlled Tool Execution

**Status:** Accepted

**Date:** 2026-08-21

## Context

Tool execution can cross a critical trust boundary. Treating model-supplied input
as commands, code, filesystem paths, URLs, or provider configuration would allow
unbounded side effects and leakage. The runtime needs a useful extension point
without granting ambient authority to models or HTTP callers.

## Decision

Trussium will execute only explicitly registered, in-process tool objects through
a dedicated `tools.executions` capability. Each tool has a stable name, immutable
public definition, Pydantic-validated JSON-object input, and an asynchronous
handler. A request identifies one registered tool and validated arguments.

The initial capability uses a positive shared timeout and returns a
provider-neutral structured result with stable HTTP failures. Tool names,
execution context, and stable outcomes may be logged; arguments, results,
credentials, and exception messages must not be logged. No tool is executable
unless application composition registers it.

## Consequences

- Models and callers have no arbitrary command, code, filesystem, network, or
  plugin authority.
- Applications retain explicit ownership of every side-effecting handler.
- Approval workflows, policy engines, remote tools, dynamic discovery, and
  agent-directed selection require separate future decisions.

## Alternatives Considered

- **Shell or subprocess execution:** rejected because command input cannot be
  safely bounded by a generic runtime.
- **Arbitrary HTTP tools:** rejected because SSRF, credentials, and egress policy
  require a separate security architecture.
- **Implicit function discovery:** rejected because declared registration is the
  auditable allowlist.
