# Agent Runtime implementation-readiness checklist

Implementation of workflow orchestration may begin only after this checklist
is reviewed against [ADR 0044](adr/0044-agent-runtime-boundary.md) and the
linked contracts.

## Contract coverage

- [ ] Tool registration, immutable metadata, discovery, and bounded execution
      match [AGENT_RUNTIME.md](AGENT_RUNTIME.md).
- [ ] Authorization, allow-list composition, and approval decisions match
      [AGENT_RUNTIME_POLICY.md](AGENT_RUNTIME_POLICY.md) and
      [AGENT_RUNTIME_APPROVAL.md](AGENT_RUNTIME_APPROVAL.md).
- [ ] Workflow states, deadlines, cancellation, and shutdown match
      [AGENT_RUNTIME_WORKFLOWS.md](AGENT_RUNTIME_WORKFLOWS.md).
- [ ] Result aggregation and error precedence match
      [AGENT_RUNTIME_RESULTS.md](AGENT_RUNTIME_RESULTS.md).

## Safety and compatibility gates

- [ ] No unrestricted code, filesystem, network, or credential access is added.
- [ ] Existing capability, provider, request-correlation, and error APIs remain
      backward compatible.
- [ ] Every new boundary has finite deadlines, bounded fan-out, and explicit
      cancellation cleanup.
- [ ] Operational events exclude prompts, arguments, outputs, credentials,
      provider payloads, and exception text.
- [ ] Policy and approval integrations remain opt-in and deployment-owned.

## Validation gates

- [ ] Deterministic unit and API tests cover happy paths and terminal-state
      precedence.
- [ ] Real-process and streaming cancellation tests cover child cleanup.
- [ ] Ruff, strict MyPy, Pytest, package, container, and Kubernetes validation
      pass.
- [ ] Runtime docs and `trussiumhq.github.io` are updated in the same change.
