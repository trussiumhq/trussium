# Agent Runtime workflow lifecycle

This contract defines bounded workflow orchestration above existing
capabilities and controlled tools. It does not implement a workflow engine.

## States

Workflow state transitions are deterministic:

```text
accepted → running → completed
                   ↘ failed
                   ↘ cancelled
                   ↘ timed_out
```

Only `running` workflows may start child capability or tool executions. A
terminal workflow cannot accept new work, and duplicate terminal transitions
are ignored.

## Execution context

The runtime assigns a workflow execution identifier and preserves the inbound
request identifier. Child capability and tool executions inherit the parent
context and receive their own execution identifiers. Context is restored when
each child completes, fails, or is cancelled.

## Deadlines and cancellation

Every workflow has an explicit finite deadline and a bounded child budget.
Caller cancellation propagates to active children cooperatively; the workflow
waits for child finalization before emitting its terminal event. A deadline
produces `timed_out` and prevents new child work. Native cancellation is never
converted into a generic provider or tool failure.

## Failure and shutdown

The first terminal failure is preserved as the workflow outcome. Sibling work
is cancelled according to the workflow policy, and cleanup runs in reverse
creation order within the remaining deadline. Graceful application shutdown
stops admission, drains active workflows, and emits bounded cancellation or
timeout events for work that exceeds the drain deadline.

## Observability and privacy

Workflow lifecycle events include request and execution identifiers, bounded
workflow identity, state transition, duration, and stable reason codes. They do
not include prompts, tool arguments or outputs, credentials, provider payloads,
or exception text.

Result aggregation and bounded error propagation are defined in [Agent Runtime
workflow results and errors](AGENT_RUNTIME_RESULTS.md).
