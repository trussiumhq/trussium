# Agent Runtime tool authorization and policy

This document defines the policy boundary for controlled tool invocations. It
extends the existing [capability authorization](AUTHORIZATION.md) allow-list;
it does not introduce a hosted policy engine.

## Pre-execution decision

Authorization is evaluated before a registered tool handler starts. Policy
receives only the authenticated identity and tenant binding, canonical tool
name and version, existing capability/provider context, and bounded invocation
metadata such as deadline and resource budget.

Raw tool arguments, credentials, arbitrary headers, provider payloads, and
implementation objects are not policy inputs.

The decision is `allow`, `deny`, or `approval_required`. A denial returns a
stable `tool_not_authorized` error and emits a bounded audit event; the handler
is not invoked. Approval is explicit, bounded, and must produce a stable
decision or `approval_timed_out`.

## Allow-list composition

An identity’s tool allow-list is intersected with the application’s registered
tools. Capability allow-lists are evaluated first, so tool policy cannot grant
access to a capability that the identity is denied.

Legacy unbound API keys remain compatible and do not gain implicit tool access;
applications must explicitly register and provide the tool executor.

## Extension boundary

Applications may provide a local asynchronous policy or approval adapter. The
adapter must obey the runtime deadline and return a stable decision. External
policy services, credential stores, and approval UIs remain deployment-owned
integrations.

The runtime exposes immutable `ToolAuthorizationRequest` and
`ToolAuthorizationResult` models plus the asynchronous `ToolPolicyAdapter`
protocol. Requests contain identity, tool metadata, execution context, and
bounded budgets only; adapters must not receive invocation arguments.
When configured on `ToolExecutor`, the policy adapter runs before argument
validation and handler invocation; omitted adapters preserve legacy execution.
The executor emits bounded `tool.authorization.requested` and
`tool.authorization.decided` events and records decisions in the
`trussium_tool_authorization_decisions` counter.

The bounded approval request and decision contract is documented in [Agent
Runtime human-approval contract](AGENT_RUNTIME_APPROVAL.md).

## Privacy and audit

Policy and audit events include correlation identifiers, identity and tool
names, decision, stable reason code, and duration. They never include arguments,
outputs, credentials, exception text, or provider-specific payloads.
