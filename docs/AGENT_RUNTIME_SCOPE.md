# Agent Runtime first workflow scope

The first workflow slice is intentionally bounded. It composes existing
capabilities and registered tools; it does not create a general-purpose
scheduler or autonomous agent loop.

The initial coordinator implementation executes one declared workflow of
sequential tool steps and explicitly declared parallel groups with the limits
below. Persistence and autonomous replanning remain outside this first slice.

Sequential steps and bounded parallel groups are now implemented by the
workflow coordinator; the limits below remain enforced at the contract
boundary. Admission validation rejects duplicate step IDs, empty or oversized
parallel groups, and workflows exceeding sixteen total child steps before any
handler starts.

## Allowed execution model

- One parent workflow per request.
- Sequential child steps and explicitly declared parallel groups.
- Maximum depth of 4 nested workflows.
- Maximum of 16 child steps per workflow and 8 concurrent children per group.
- A finite workflow deadline inherited from the request and bounded by runtime
  configuration.

Each child must be declared before execution, use an existing capability or
registered tool, and inherit the parent execution context. Dynamic discovery
may select from sealed registries but may not create hidden handlers.

## Side-effect boundaries

The workflow may pass typed, bounded results between declared steps. It may not
execute arbitrary code, access the filesystem or network implicitly, inject
credentials, or persist state unless an explicitly registered tool owns that
side effect and policy authorizes it.

Retries, fallback, and provider routing remain governed by their existing
contracts; the workflow does not multiply those policies autonomously.

## Admission and termination

Admission fails before child execution when depth, fan-out, deadline, or policy
limits are exceeded. Caller cancellation and deadline timeout stop admission,
cancel active children cooperatively, and preserve the workflow result and error
precedence contracts. Cleanup runs in reverse declaration order.

## Non-goals

- unbounded recursion or fan-out;
- autonomous replanning loops;
- implicit retries or provider selection;
- durable workflow storage;
- multi-agent communication or memory; and
- a hosted scheduler, approval service, or policy engine.
