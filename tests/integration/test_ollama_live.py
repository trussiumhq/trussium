"""Opt-in compatibility tests against a real local Ollama server."""

import json
import os
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from time import monotonic, sleep
from typing import cast

import httpx
import pytest

from tests.integration.harness import (
    ManagedProcess,
    reserve_loopback_port,
    start_process,
    wait_until_ready,
)

pytestmark = [pytest.mark.integration, pytest.mark.ollama]

_DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"


@dataclass(frozen=True)
class LiveOllamaRuntime:
    """Production Trussium process backed by a real Ollama server."""

    base_url: str
    model: str
    process: ManagedProcess

    def wait_for_terminal_log(
        self,
        *,
        request_id: str,
    ) -> list[dict[str, object]]:
        """Wait for one request lifecycle to finish in captured logs."""
        deadline = monotonic() + 10

        while monotonic() < deadline:
            records: list[dict[str, object]] = []

            for line in self.process.output().splitlines():
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if isinstance(payload, dict) and payload.get("request_id") == request_id:
                    records.append(payload)

            if any(record.get("event") == "http.request.completed" for record in records):
                return records

            sleep(0.05)

        raise AssertionError(
            f"Timed out waiting for logs for {request_id!r}.\n"
            f"Runtime output:\n{self.process.output()}"
        )


def _available_ollama_models(base_url: str) -> set[str]:
    """Return model identifiers advertised by the compatible endpoint."""
    try:
        response = httpx.get(
            f"{base_url.rstrip('/')}/models",
            timeout=5,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        pytest.skip(f"Ollama is unavailable at {base_url}: {error}")

    payload = cast(dict[str, object], response.json())
    data = cast(list[dict[str, object]], payload.get("data", []))
    return {str(item["id"]) for item in data}


@pytest.fixture(scope="module")
def live_ollama_runtime(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[LiveOllamaRuntime]:
    """Start production Trussium when live Ollama validation is enabled."""
    model = os.getenv("TRUSSIUM_OLLAMA_TEST_MODEL", "").strip()

    if not model:
        pytest.skip("Set TRUSSIUM_OLLAMA_TEST_MODEL to run live Ollama compatibility tests.")

    provider_base_url = os.getenv(
        "TRUSSIUM_OLLAMA_TEST_BASE_URL",
        _DEFAULT_OLLAMA_BASE_URL,
    ).rstrip("/")
    available_models = _available_ollama_models(provider_base_url)

    if model not in available_models:
        pytest.skip(
            f"Ollama model {model!r} is not installed; available models: "
            f"{sorted(available_models)!r}"
        )

    repository_root = Path(__file__).resolve().parents[2]
    log_directory = tmp_path_factory.mktemp("live-ollama-process-logs")
    runtime_port = reserve_loopback_port()
    runtime_base_url = f"http://127.0.0.1:{runtime_port}"
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONUNBUFFERED": "1",
            "TRUSSIUM_PROVIDER__NAME": "ollama",
            "TRUSSIUM_PROVIDER__BASE_URL": provider_base_url,
            "TRUSSIUM_RUNTIME__HOST": "127.0.0.1",
            "TRUSSIUM_RUNTIME__PORT": str(runtime_port),
            "TRUSSIUM_TIMEOUTS__PROVIDER_REQUEST_SECONDS": "120",
            "TRUSSIUM_TIMEOUTS__STREAM_IDLE_SECONDS": "60",
        }
    )
    process = start_process(
        [sys.executable, "-m", "trussium"],
        cwd=repository_root,
        environment=environment,
        log_path=log_directory / "trussium-ollama.log",
    )

    try:
        wait_until_ready(
            f"{runtime_base_url}/health/ready",
            process=process,
        )
        yield LiveOllamaRuntime(
            base_url=runtime_base_url,
            model=model,
            process=process,
        )
    finally:
        process.stop()


def _chat_request(
    runtime: LiveOllamaRuntime,
    *,
    streaming: bool,
) -> dict[str, object]:
    """Create a bounded live-model request."""
    return {
        "model": runtime.model,
        "messages": [
            {
                "role": "user",
                "content": "Reply with one brief greeting for a compatibility test.",
            }
        ],
        "temperature": 0,
        "max_output_tokens": 24,
        "stream": streaming,
    }


def _assert_live_lifecycle(
    runtime: LiveOllamaRuntime,
    *,
    request_id: str,
) -> None:
    """Assert the successful provider-aware lifecycle."""
    records = runtime.wait_for_terminal_log(request_id=request_id)

    assert [record["event"] for record in records] == [
        "http.request.started",
        "capability.execution.started",
        "provider.execution.started",
        "provider.execution.completed",
        "capability.execution.completed",
        "http.request.completed",
    ]
    assert all(
        record["provider"] == "ollama"
        for record in records
        if str(record["event"]).startswith("provider.")
    )
    assert "compatibility test" not in json.dumps(records)


def test_live_ollama_json_completion(
    live_ollama_runtime: LiveOllamaRuntime,
) -> None:
    """A real Ollama JSON response should satisfy Trussium's contract."""
    request_id = "live-ollama-json-59"
    response = httpx.post(
        f"{live_ollama_runtime.base_url}/v1/chat/completions",
        headers={"X-Request-ID": request_id},
        json=_chat_request(live_ollama_runtime, streaming=False),
        timeout=130,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "ollama"
    assert payload["model"] == live_ollama_runtime.model
    assert payload["choices"][0]["message"]["content"].strip()
    assert payload["usage"]["total_tokens"] > 0
    _assert_live_lifecycle(live_ollama_runtime, request_id=request_id)


def test_live_ollama_streaming_completion(
    live_ollama_runtime: LiveOllamaRuntime,
) -> None:
    """A real Ollama stream should normalize through Trussium's SSE API."""
    request_id = "live-ollama-stream-59"

    with httpx.stream(
        "POST",
        f"{live_ollama_runtime.base_url}/v1/chat/completions",
        headers={"X-Request-ID": request_id},
        json=_chat_request(live_ollama_runtime, streaming=True),
        timeout=130,
    ) as response:
        blocks = "".join(response.iter_text()).strip().split("\n\n")
        status_code = response.status_code

    events = [
        (
            block.splitlines()[0].removeprefix("event: "),
            cast(
                dict[str, object],
                json.loads(block.splitlines()[1].removeprefix("data: ")),
            ),
        )
        for block in blocks
    ]
    assert status_code == 200
    assert events[0][0] == "start"
    assert events[0][1]["provider"] == "ollama"
    assert events[0][1]["model"] == live_ollama_runtime.model
    assert any(name == "delta" and payload["content"] for name, payload in events)
    assert events[-1][0] == "end"
    assert cast(dict[str, int], events[-1][1]["usage"])["total_tokens"] > 0
    _assert_live_lifecycle(live_ollama_runtime, request_id=request_id)
