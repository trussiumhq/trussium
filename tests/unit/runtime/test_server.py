"""Production server configuration tests."""

import asyncio
import io
import json
from collections.abc import Iterable

import pytest
from fastapi import FastAPI
from uvicorn.lifespan.off import LifespanOff

from trussium.config.settings import RuntimeSettings
from trussium.observability import configure_logging
from trussium.runtime.server import (
    GracefulShutdownServer,
    create_server,
)


def test_create_server_applies_runtime_settings() -> None:
    """The typed drain deadline should reach Uvicorn's server config."""
    application = FastAPI()
    settings = RuntimeSettings(
        host="127.0.0.1",
        port=9042,
        graceful_shutdown_seconds=7,
    )

    server = create_server(
        application,
        settings=settings,
    )

    assert isinstance(server, GracefulShutdownServer)
    assert server.config.app is application
    assert server.config.host == "127.0.0.1"
    assert server.config.port == 9042
    assert server.config.timeout_graceful_shutdown == 7


def test_shutdown_emits_structured_lifecycle_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An ordinary drain should emit one started and completed event."""
    output = io.StringIO()
    configure_logging(stream=output)
    server = create_server(FastAPI(), settings=RuntimeSettings())
    server.servers = []
    server.lifespan = LifespanOff(server.config)

    async def complete_drain() -> None:
        return None

    monkeypatch.setattr(server, "_wait_tasks_to_complete", complete_drain)

    asyncio.run(server.shutdown())

    payloads = [json.loads(line) for line in output.getvalue().splitlines()]
    assert [payload["event"] for payload in payloads] == [
        "runtime.shutdown.started",
        "runtime.shutdown.completed",
    ]
    assert payloads[0]["active_tasks"] == 0
    assert payloads[0]["graceful_shutdown_seconds"] == 30
    assert payloads[1]["outcome"] == "completed"


def test_shutdown_timeout_emits_bounded_failure_and_cancels_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An over-deadline task should be cancelled and reported without task data."""
    output = io.StringIO()
    configure_logging(stream=output)
    server = create_server(
        FastAPI(),
        settings=RuntimeSettings(graceful_shutdown_seconds=1),
    )
    server.servers = []
    server.lifespan = LifespanOff(server.config)

    async def exercise_timeout() -> None:
        async def wait_forever() -> None:
            await asyncio.Event().wait()

        task = asyncio.create_task(wait_forever(), name="secret-task-name")
        server.server_state.tasks.add(task)

        async def time_out_drain() -> None:
            raise TimeoutError

        async def leave_task_unfinished(
            tasks: Iterable[asyncio.Task[None]],
            *,
            timeout: float | None = None,
        ) -> tuple[set[asyncio.Task[None]], set[asyncio.Task[None]]]:
            _ = timeout
            task_set = set(tasks)
            return set(), task_set

        monkeypatch.setattr(server, "_wait_tasks_to_complete", time_out_drain)
        monkeypatch.setattr("trussium.runtime.server.asyncio.wait", leave_task_unfinished)
        await server.shutdown()

        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise_timeout())

    payloads = [json.loads(line) for line in output.getvalue().splitlines()]
    assert [payload["event"] for payload in payloads] == [
        "runtime.shutdown.started",
        "runtime.shutdown.drain_timeout",
        "runtime.shutdown.cleanup_timeout",
        "runtime.shutdown.completed",
    ]
    assert payloads[1]["error_code"] == "graceful_shutdown_timeout"
    assert payloads[1]["active_tasks"] == 1
    assert payloads[2]["error_code"] == "cancellation_cleanup_timeout"
    assert payloads[2]["unfinished_tasks"] == 1
    assert payloads[3]["outcome"] == "forced"
    assert "secret-task-name" not in output.getvalue()
