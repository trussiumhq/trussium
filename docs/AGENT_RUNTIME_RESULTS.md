# Agent Runtime workflow results and errors

This contract defines deterministic aggregation of child capability and tool
outcomes for the bounded workflow API.

## Result aggregation

A workflow result contains an immutable workflow identifier, terminal status,
ordered child summaries, and bounded usage metadata. Child outputs are retained
only when the workflow contract explicitly requests them; payloads are never
written to operational logs.

The aggregate status is deterministic:

| Child outcomes | Workflow status |
| --- | --- |
| All completed | `completed` |
| At least one failed and no cancellation/timeout | `failed` |
| Any child cancelled by caller or policy | `cancelled` |
| Any deadline exceeded | `timed_out` |

Cancellation and timeout take precedence over ordinary failure. Within the
same class, the first terminal child outcome is preserved as the workflow’s
primary reason; later outcomes remain bounded summaries.

## Error propagation

Typed capability, provider, and tool errors retain their stable public code and
safe message. The workflow wraps them with workflow and child correlation IDs
without changing the underlying category. Unexpected exceptions normalize to a
stable `workflow_execution_failed` error; exception text and tracebacks remain
internal diagnostics.

Native caller cancellation is re-raised unchanged. A workflow never retries,
substitutes, or suppresses a child error unless an explicit reviewed policy
allows that behavior.

## Observability

Terminal workflow events include workflow and child execution identifiers,
status, primary reason code, duration, and bounded child counts. They exclude
prompts, tool arguments or outputs, credentials, provider payloads, and raw
exception text.

## Audit record

`WorkflowAuditRecord` is the storage-neutral immutable envelope for downstream
audit consumers. It contains the event, timestamp, request/execution identity,
optional status and reason code, and bounded step/group counts. It deliberately
has no payload fields. Persistence, retention, export, and external audit
services remain deployment-owned follow-up work.

Applications may inject an asynchronous `WorkflowAuditSink` to receive records.
The default sink discards them, and sink failures are isolated from workflow
execution so observability cannot change the execution outcome.
