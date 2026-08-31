# Agent Runtime tool and invocation contract

This document defines the first implementation-independent contract for the
deferred Agent Runtime described in [ADR 0044](adr/0044-agent-runtime-boundary.md).

Trussium already provides the first controlled tool-execution foundation:
`ToolRegistry`, immutable tool contracts, a bounded `ToolExecutor`, structured
lifecycle events, and `POST /v1/tools/executions`. Registered tools expose
bounded version and description metadata through `GET /v1/tools`. This document describes the
contract boundary and the additional workflow/agent orchestration that remains
deferred.

## Tool registration

A tool is explicitly registered with:

- a stable, non-blank name;
- a semantic version;
- an immutable input schema;
- an owner-provided asynchronous handler; and
- bounded metadata describing authorization and resource limits.

Registration is application-owned and opt-in. Duplicate names or invalid
schemas fail before the registry is sealed. Discovery returns metadata only; it
never exposes credentials, implementation details, or hidden network access.

## Invocation

An invocation receives an immutable input value and inherited execution context.
The runtime assigns a child execution identifier while preserving the request
identifier and parent relationship. A handler may return a JSON-compatible
result or a typed tool error; arbitrary exception text is not exposed to the
caller.

The lifecycle is deterministic:

```text
accepted → started → completed
                    ↘ failed
                    ↘ cancelled
                    ↘ timed_out
```

Each invocation has an explicit deadline, cancellation signal, and resource
budget. Cancellation and timeout are cooperative, preserve native cancellation
semantics, and always finalize the handler before the parent workflow advances.

## Policy and authorization

Authorization is evaluated before a handler starts. Policy receives the stable
tool identity, caller identity, capability context, and bounded invocation
metadata—not raw credentials or payloads. A denied invocation produces a stable
policy error and no handler side effect.

Human approval is an explicit asynchronous policy extension. It must have a
bounded wait, a stable decision, and an auditable outcome; approval is never
implicit because a tool is registered.

Detailed composition with identity bindings is defined in [Agent Runtime tool
authorization and policy](AGENT_RUNTIME_POLICY.md).

## Audit and privacy

The runtime emits bounded structured events for accepted, started, completed,
failed, cancelled, timed-out, denied, and approval-pending invocations. Events
include correlation identifiers, tool identity, outcome, duration, and stable
error codes. They exclude tool inputs, outputs, credentials, arbitrary headers,
provider payloads, and exception text.

## Non-goals for the first slice

- unrestricted Python or shell execution;
- implicit network or filesystem access;
- hidden credential injection;
- unbounded retries, recursion, or fan-out;
- a hosted policy or approval service; and
- a second execution path that bypasses capability and provider contracts.

Workflow orchestration, multi-step agent state, memory, multi-agent
communication, and human-approval integrations remain deferred until their
contracts are separately reviewed.
