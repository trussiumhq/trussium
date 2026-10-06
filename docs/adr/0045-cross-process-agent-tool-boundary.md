# ADR 0045: Cross-process agent tool boundary

## Status

Proposed — the fixed MCP adapter is implemented in this change; end-to-end
Knowledge Agent integration and the remaining acceptance criteria are tracked
by [issue #466](https://github.com/trussiumhq/trussium/issues/466).

## Context

The bounded workflow and tool APIs currently compose an application-owned
`ToolExecutor` in process. This is the preferred boundary for application
tools, but it does not by itself connect separately deployed applications
such as `trussium-knowledge-agent` to a runtime process. Adding a workflow
method to an SDK would only call the endpoint; it would not configure any tools
on the packaged runtime.

The existing [controlled-tool decision](0006-controlled-tool-execution.md)
rejects arbitrary HTTP tools because request-controlled URLs, credentials, and
egress create SSRF and data-leak risks. Any cross-process integration must keep
the same explicit registration and policy properties.

## Proposed decision

Use an application-composed remote MCP adapter for cross-process tools. The
adapter is configured at trusted application startup with a fixed endpoint,
fixed remote tool names, typed argument contracts, and operator-supplied
credentials. It exposes those tools to the existing local `ToolRegistry` as
ordinary registered tools; the existing `ToolExecutor` remains the only path
for authorization, approval, deadlines, cancellation, error normalization,
execution context, and audit events.

The initial adapter implements the fixed endpoint, static remote tool name,
typed argument model, authentication, size/deadline limits, redirect and
ambient-proxy protections, safe errors, and correlation propagation. It does
not by itself configure the packaged command or implement the Knowledge Agent
tool server; those end-to-end pieces remain tracked by issue #466.

The adapter must not perform request-time tool discovery. Workflow requests may
select only tools in the local sealed registry and can never select or modify a
remote URL, credential, or remote tool name. The adapter must reject redirects,
bound response sizes and timeouts, use authenticated transport, avoid ambient
proxy settings unless explicitly configured, and propagate only approved
correlation metadata. Arguments, outputs, credentials, and remote exception
details remain excluded from logs and audit records.

The Knowledge Agent's tool server will expose only its documented, read-only
operations and require explicit authentication. External repository writes
remain a separate feature requiring human approval and are not part of this
integration.

## Consequences

- Separately deployed applications can participate in bounded workflows
  without importing runtime internals or granting the runtime unrestricted
  network access.
- Every remote destination and tool contract is reviewable in application
  composition and remains absent from workflow request payloads.
- Remote availability becomes an application dependency; calls must fit within
  the parent tool and workflow deadlines and preserve cancellation.
- A typed Python SDK method is useful only after the remote tool composition
  contract is implemented; it does not replace that contract.
- The packaged runtime remains tool-free unless its application explicitly
  composes a tool executor.

## Implementation requirements

- Validate fixed HTTPS endpoints at composition time. Plain HTTP, when needed
  for local development, must require explicit opt-in and remain restricted to
  local or controlled networks.
- Keep remote endpoint selection, remote tool names, argument models, and
  credentials outside user and model inputs.
- Apply the runtime's existing admission, identity policy, approval, timeout,
  cancellation, and bounded audit behavior before any outbound request.
- Propagate request and execution identifiers only; do not forward arbitrary
  inbound headers, baggage, model prompts, or provider payloads.
- Disable redirects and prevent ambient proxy configuration by default.
- Bound request and response sizes and normalize transport and protocol errors
  to stable tool failures.
- Test that unknown tools, invalid schemas, endpoint overrides, redirects,
  oversized responses, timeouts, cancellation, and secret/log leakage cause no
  unapproved activity.

## Alternatives considered

- **Add only an SDK workflow method:** rejected as incomplete because the
  packaged runtime has no tools unless the application explicitly registers
  them.
- **Allow arbitrary HTTP tools in workflow requests:** rejected because callers
  or model output could select destinations and create SSRF or credential
  disclosure paths.
- **Dynamically discover every tool from a remote MCP server:** rejected for
  the initial integration because it makes the effective allowlist depend on
  remote runtime state rather than reviewed application composition.
- **Co-locate the Knowledge Agent and runtime in one process:** rejected for
  this integration because it couples separately deployed services and
  increases dependency and lifecycle coupling.

## References

- [Controlled tool execution](../TOOL_EXECUTION.md)
- [MCP integration](../MCP.md)
- [Agent Runtime boundary](0044-agent-runtime-boundary.md)
- [Integration issue #466](https://github.com/trussiumhq/trussium/issues/466)
