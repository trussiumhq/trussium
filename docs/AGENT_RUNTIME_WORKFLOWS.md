# Agent Runtime workflow lifecycle

This contract defines bounded workflow orchestration above existing
capabilities and controlled tools. The first bounded coordinator is available
through `POST /v1/workflows/executions`; durable and distributed workflow
engines remain out of scope.

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

The coordinator’s timeout and caller-cancellation paths are regression-tested.
Active parallel children are cancelled and finalized before cancellation
propagates to the caller.

## Lifecycle events

The coordinator emits structured `workflow.*` events for start, completion,
timeout, cancellation, and admission rejection. Events inherit the request and
execution context and contain only bounded counts, status, and stable rejection
codes. Tool arguments and outputs are never included in workflow logs.

## Failure and shutdown

The first terminal failure is preserved as the workflow outcome. Sibling work
is cancelled according to the workflow policy, and cleanup runs in reverse
creation order within the remaining deadline. Graceful application shutdown
stops admission, drains active workflows, and emits bounded cancellation or
timeout events for work that exceeds the drain deadline.

The local `WorkflowLifecycle` coordinator exposes this contract directly:
`begin_shutdown()` stops admission, `active_count` reports in-flight work, and
`drain(timeout_seconds)` waits for active executions with a finite deadline.
The coordinator transitions from `running` to `draining` to `stopped`; it does
not coordinate across processes or clusters.

The FastAPI application invokes this drain during lifespan shutdown using the
runtime graceful-shutdown budget, before capability, provider, and service
teardown. A drain timeout is logged as an operational event and does not expose
tool payloads or raw exception text.

When metrics are enabled, the runtime exposes active workflow gauges and
bounded counters for terminal outcomes, admission rejection codes, and
shutdown drain outcomes. Labels are stable low-cardinality values; tool names,
arguments, and outputs are never metric labels.

## Observability and privacy

Workflow lifecycle events include request and execution identifiers, bounded
workflow identity, state transition, duration, and stable reason codes. They do
not include prompts, tool arguments or outputs, credentials, provider payloads,
or exception text.

Result aggregation and bounded error propagation are defined in [Agent Runtime
workflow results and errors](AGENT_RUNTIME_RESULTS.md).
