"""Real-process validation for graceful shutdown under active workloads."""

import json
import signal
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest

from tests.integration.harness import (
    IntegrationRuntime,
    create_integration_runtime,
)

pytestmark = pytest.mark.integration

_JSON_MODEL = "e2e-shutdown-json"
_STREAM_MODEL = "e2e-shutdown-stream"


@dataclass(frozen=True)
class StreamResult:
    """Observed response state for a real streaming client."""

    status_code: int
    request_id: str
    body: str
    interrupted: bool


def _chat_request(*, model: str, streaming: bool = False) -> dict[str, object]:
    """Build a controlled integration chat request."""
    return {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Graceful shutdown integration prompt.",
            }
        ],
        "stream": streaming,
    }


@contextmanager
def _running_runtime(
    tmp_path: Path,
    *,
    graceful_shutdown_seconds: int,
) -> Iterator[IntegrationRuntime]:
    """Start and always clean up a dedicated production runtime pair."""
    repository_root = Path(__file__).resolve().parents[2]
    log_directory = tmp_path / "process-logs"
    log_directory.mkdir()
    runtime = create_integration_runtime(
        repository_root=repository_root,
        log_directory=log_directory,
        graceful_shutdown_seconds=graceful_shutdown_seconds,
    )

    try:
        yield runtime
    finally:
        runtime.runtime_process.stop()
        runtime.fake_openai_process.stop()


def _complete_json_request(
    base_url: str,
    *,
    request_id: str,
) -> httpx.Response:
    """Execute a controlled non-streaming request from a worker thread."""
    return httpx.post(
        f"{base_url}/v1/chat/completions",
        headers={"X-Request-ID": request_id},
        json=_chat_request(model=_JSON_MODEL),
        timeout=10,
    )


def _consume_stream(
    base_url: str,
    *,
    request_id: str,
) -> StreamResult:
    """Consume a controlled SSE response and retain partial data on shutdown."""
    status_code = 0
    response_request_id = ""
    chunks: list[str] = []
    interrupted = False

    try:
        with httpx.stream(
            "POST",
            f"{base_url}/v1/chat/completions",
            headers={"X-Request-ID": request_id},
            json=_chat_request(
                model=_STREAM_MODEL,
                streaming=True,
            ),
            timeout=10,
        ) as response:
            status_code = response.status_code
            response_request_id = response.headers["x-request-id"]
            chunks.extend(response.iter_text())
    except httpx.RemoteProtocolError:
        interrupted = True

    return StreamResult(
        status_code=status_code,
        request_id=response_request_id,
        body="".join(chunks),
        interrupted=interrupted,
    )


def _assert_lifecycle(
    runtime: IntegrationRuntime,
    *,
    request_id: str,
    expected_events: list[str],
) -> list[dict[str, object]]:
    """Assert exact, correlated, non-duplicated request lifecycle events."""
    records = runtime.structured_logs(request_id=request_id)

    assert [record["event"] for record in records] == expected_events
    assert all(record["request_id"] == request_id for record in records)
    assert len({record["execution_id"] for record in records}) == 1
    assert "Graceful shutdown integration prompt." not in json.dumps(records)
    return records


def _assert_graceful_process_exit(runtime: IntegrationRuntime) -> None:
    """Accept normal or signal-aware exit after Uvicorn completes shutdown."""
    return_code = runtime.runtime_process.wait_for_exit()

    assert return_code in {0, -signal.SIGTERM}
    assert "Application shutdown complete." in runtime.runtime_process.output()
    assert "Finished server process" in runtime.runtime_process.output()


def test_active_json_request_drains_before_shutdown_deadline(
    tmp_path: Path,
) -> None:
    """SIGTERM should preserve an active JSON response inside the grace period."""
    request_id = "shutdown-drain-json-67"

    with _running_runtime(
        tmp_path,
        graceful_shutdown_seconds=3,
    ) as runtime:
        with ThreadPoolExecutor(max_workers=1) as executor:
            response_future = executor.submit(
                _complete_json_request,
                runtime.base_url,
                request_id=request_id,
            )
            runtime.wait_for_provider_state(
                model=_JSON_MODEL,
                state="active",
            )

            runtime.runtime_process.send_sigterm()
            runtime.wait_until_not_accepting_requests()
            assert runtime.runtime_process.process.poll() is None

            runtime.release_provider_workload(model=_JSON_MODEL)
            response = response_future.result(timeout=5)

        assert response.status_code == 200
        assert response.headers["x-request-id"] == request_id
        assert response.json()["model"] == _JSON_MODEL
        _assert_graceful_process_exit(runtime)
        provider_state = runtime.wait_for_provider_state(
            model=_JSON_MODEL,
            state="finalized",
        )
        assert provider_state["completed"] is True
        _assert_lifecycle(
            runtime,
            request_id=request_id,
            expected_events=[
                "http.request.started",
                "capability.execution.started",
                "provider.execution.started",
                "provider.execution.completed",
                "capability.execution.completed",
                "http.request.completed",
            ],
        )


def test_active_stream_drains_before_shutdown_deadline(
    tmp_path: Path,
) -> None:
    """SIGTERM should let an active SSE response finish inside the deadline."""
    request_id = "shutdown-drain-stream-67"

    with _running_runtime(
        tmp_path,
        graceful_shutdown_seconds=3,
    ) as runtime:
        with ThreadPoolExecutor(max_workers=1) as executor:
            response_future = executor.submit(
                _consume_stream,
                runtime.base_url,
                request_id=request_id,
            )
            runtime.wait_for_provider_state(
                model=_STREAM_MODEL,
                state="active",
            )

            runtime.runtime_process.send_sigterm()
            runtime.wait_until_not_accepting_requests()
            assert runtime.runtime_process.process.poll() is None

            runtime.release_provider_workload(model=_STREAM_MODEL)
            result = response_future.result(timeout=5)

        assert result.status_code == 200
        assert result.request_id == request_id
        assert result.interrupted is False
        assert "event: start" in result.body
        assert "event: end" in result.body
        _assert_graceful_process_exit(runtime)
        provider_state = runtime.wait_for_provider_state(
            model=_STREAM_MODEL,
            state="finalized",
        )
        assert provider_state["completed"] is True
        records = _assert_lifecycle(
            runtime,
            request_id=request_id,
            expected_events=[
                "http.request.started",
                "capability.execution.started",
                "provider.execution.started",
                "provider.execution.completed",
                "capability.execution.completed",
                "http.request.completed",
            ],
        )
        assert all(record.get("streaming") is True for record in records[1:-1])


def test_over_deadline_stream_is_cancelled_and_finalized(
    tmp_path: Path,
) -> None:
    """An SSE stream exceeding the grace period should unwind cooperatively."""
    request_id = "shutdown-timeout-stream-67"

    with _running_runtime(
        tmp_path,
        graceful_shutdown_seconds=1,
    ) as runtime:
        with ThreadPoolExecutor(max_workers=1) as executor:
            response_future = executor.submit(
                _consume_stream,
                runtime.base_url,
                request_id=request_id,
            )
            runtime.wait_for_provider_state(
                model=_STREAM_MODEL,
                state="active",
            )

            runtime.runtime_process.send_sigterm()
            runtime.wait_until_not_accepting_requests()
            result = response_future.result(timeout=5)

        assert result.status_code == 200
        assert result.request_id == request_id
        assert "event: start" in result.body
        assert "event: end" not in result.body
        _assert_graceful_process_exit(runtime)
        provider_state = runtime.wait_for_provider_state(
            model=_STREAM_MODEL,
            state="finalized",
        )
        assert provider_state["completed"] is False
        records = _assert_lifecycle(
            runtime,
            request_id=request_id,
            expected_events=[
                "http.request.started",
                "capability.execution.started",
                "provider.execution.started",
                "provider.execution.cancelled",
                "capability.execution.cancelled",
                "http.request.cancelled",
            ],
        )
        assert all(record.get("cancellation_reason") == "task_cancelled" for record in records[3:])
        runtime_output = runtime.runtime_process.output()
        assert runtime_output.index("http.request.cancelled") < runtime_output.index(
            "Application shutdown complete."
        )
