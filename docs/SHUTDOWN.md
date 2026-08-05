# Graceful Shutdown Guide

Trussium drains active HTTP requests and server-sent event streams when the
production process receives `SIGTERM` or `SIGINT`.

## Runtime contract

The default shutdown sequence is:

1. Uvicorn closes the listening socket so the process stops accepting new
   connections.
2. Active JSON responses and SSE streams may finish during the configured
   grace period.
3. When the grace period expires, Uvicorn cancels remaining request tasks.
4. Trussium gives cancelled tasks up to one additional second to finalize
   capability, provider, SDK stream, and HTTP resources.
5. Application shutdown completes and the process exits.

Completed work retains its normal correlated `provider.execution.completed`,
`capability.execution.completed`, and `http.request.completed` events. Work
cancelled after the deadline emits the corresponding `cancelled` events once,
with `cancellation_reason` set to `task_cancelled` and the original request and
execution identifiers.

## Configuration

`TRUSSIUM_RUNTIME__GRACEFUL_SHUTDOWN_SECONDS` sets the positive whole-number
grace period. The default is 30 seconds.

```bash
export TRUSSIUM_RUNTIME__GRACEFUL_SHUTDOWN_SECONDS=20
uv run python -m trussium
```

This deadline is independent of the provider request and stream-idle
deadlines. Provider timeouts protect steady-state execution; the graceful
shutdown deadline bounds how long a terminating process waits for active work.

## Deployment timing

The platform stop timeout must exceed the configured Trussium grace period,
the one-second cancellation-cleanup bound, and normal process-exit overhead.
A minimum margin of five seconds is recommended.

For a 20-second Trussium grace period, configure the orchestrator or container
runtime to allow at least 26 seconds before sending `SIGKILL`.

```bash
docker stop --time 26 trussium
```

The process may report exit status 143 when the native Python entry point
re-raises the handled `SIGTERM`; container runtimes can normalize a completed
stop to zero. In either case, the authoritative graceful-exit evidence is the
`Application shutdown complete.` and `Finished server process` log sequence,
with no forced kill.

## Validation

The deterministic process suite starts the real production entry point and a
controllable OpenAI-compatible provider. It proves:

- Active non-streaming work completes inside the grace period.
- Active SSE work completes inside the grace period.
- The listening socket closes while active work drains.
- An over-deadline SSE stream is cancelled and its upstream iterator is
  finalized.
- HTTP, capability, and provider terminal lifecycle events remain correlated
  and non-duplicated.
- Process exit is bounded and application shutdown completes.

Run it locally with:

```bash
uv run pytest tests/integration/test_graceful_shutdown.py
```
