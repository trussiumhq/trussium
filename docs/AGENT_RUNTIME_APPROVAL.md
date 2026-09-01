# Agent Runtime human-approval contract

Human approval is an optional policy extension for controlled tool invocations.
It is not a hosted service and is never implied by tool registration.

## Approval request

An approval request contains an immutable request ID, parent execution ID,
canonical tool name and version, requesting identity, creation time, expiry, and
a bounded reason code. It must not contain tool arguments, credentials,
provider payloads, or generated content.

The request is created only after authorization returns `approval_required` and
before the tool handler starts. The runtime exposes the request to a
deployment-owned approval adapter.

## Decisions

The adapter returns exactly one decision:

- `approved` — the invocation may start before expiry;
- `denied` — the invocation terminates with stable `tool_not_authorized`; or
- `expired` — the invocation terminates with stable `approval_timed_out`.

Duplicate, late, or contradictory decisions are ignored after the request is
terminal. Caller cancellation terminates a pending request without invoking the
handler and preserves native cancellation semantics.

## Bounds and audit

Approval waits obey the invocation deadline and a configured maximum wait. The
runtime emits bounded approval-requested, approval-decided, approval-expired,
and approval-cancelled events containing correlation IDs, tool identity,
decision, reason code, and duration. Payloads, credentials, UI details, and
exception text are excluded.

Approval adapters are optional, local integration points. The runtime does not
ship an approval UI, persistence layer, notification channel, or external
policy service.

The public integration point is the asynchronous `ToolApprovalAdapter` protocol,
which accepts an immutable `ToolApprovalRequest` and returns a
`ToolApprovalResult`. The request carries only correlation, tool, identity,
expiry, and stable reason metadata.
When policy returns `approval_required`, `ToolExecutor` waits for the configured
finite approval bound before starting the handler; a missing adapter or timeout
prevents invocation.
The executor emits bounded approval requested, decided, and expired events and
records terminal decisions in the `trussium_tool_approval_decisions` counter.
