"""End-to-end tests for Ollama's OpenAI-compatible runtime path."""

import json
from typing import cast

import httpx
import pytest

from tests.integration.harness import IntegrationRuntime

pytestmark = pytest.mark.integration


def _request(*, streaming: bool) -> dict[str, object]:
    """Create a deterministic Ollama-compatible chat request."""
    return {
        "model": "ollama-e2e-model",
        "messages": [{"role": "user", "content": "Ollama secret prompt."}],
        "temperature": 0.1,
        "max_output_tokens": 24,
        "stream": streaming,
    }


def _parse_sse(body: str) -> list[tuple[str, dict[str, object]]]:
    """Parse normalized Trussium server-sent events."""
    events: list[tuple[str, dict[str, object]]] = []

    for block in body.strip().split("\n\n"):
        lines = block.splitlines()
        events.append(
            (
                lines[0].removeprefix("event: "),
                cast(
                    dict[str, object],
                    json.loads(lines[1].removeprefix("data: ")),
                ),
            )
        )

    return events


def _assert_ollama_lifecycle(
    runtime: IntegrationRuntime,
    *,
    request_id: str,
) -> None:
    """Assert provider-aware correlated lifecycle metadata."""
    records = runtime.wait_for_terminal_log(
        request_id=request_id,
        event="http.request.completed",
    )

    assert [record["event"] for record in records] == [
        "http.request.started",
        "capability.execution.started",
        "provider.execution.started",
        "provider.execution.completed",
        "capability.execution.completed",
        "http.request.completed",
    ]
    provider_records = records[2:4]
    assert all(record["provider"] == "ollama" for record in provider_records)
    assert all(record["model"] == "ollama-e2e-model" for record in provider_records)
    assert "Ollama secret prompt." not in json.dumps(records)
    assert "e2e-test-api-key" not in json.dumps(records)


def test_ollama_compatible_json_path_reports_provider_identity(
    ollama_compatible_runtime: IntegrationRuntime,
) -> None:
    """JSON execution should identify Ollama across API and logs."""
    request_id = "e2e-ollama-json-59"
    response = httpx.post(
        f"{ollama_compatible_runtime.base_url}/v1/chat/completions",
        headers={"X-Request-ID": request_id},
        json=_request(streaming=False),
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "ollama"
    assert payload["model"] == "ollama-e2e-model"
    assert payload["choices"][0]["message"]["content"] == ("Hello from the end-to-end provider.")
    assert payload["usage"] == {
        "input_tokens": 3,
        "output_tokens": 5,
        "total_tokens": 8,
    }
    _assert_ollama_lifecycle(
        ollama_compatible_runtime,
        request_id=request_id,
    )


def test_ollama_compatible_stream_reports_provider_identity(
    ollama_compatible_runtime: IntegrationRuntime,
) -> None:
    """SSE execution should identify Ollama and preserve normalized events."""
    request_id = "e2e-ollama-stream-59"

    with httpx.stream(
        "POST",
        f"{ollama_compatible_runtime.base_url}/v1/chat/completions",
        headers={"X-Request-ID": request_id},
        json=_request(streaming=True),
        timeout=5,
    ) as response:
        events = _parse_sse("".join(response.iter_text()))
        status_code = response.status_code

    assert status_code == 200
    assert events[0] == (
        "start",
        {
            "type": "start",
            "id": "resp_e2e_stream",
            "provider": "ollama",
            "model": "ollama-e2e-model",
        },
    )
    assert [event_name for event_name, _ in events] == [
        "start",
        "delta",
        "delta",
        "end",
    ]
    assert (
        "".join(str(payload["content"]) for event_name, payload in events if event_name == "delta")
        == "Hello from the integration stream."
    )
    _assert_ollama_lifecycle(
        ollama_compatible_runtime,
        request_id=request_id,
    )
