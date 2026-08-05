"""End-to-end tests for Trussium's first chat vertical slice."""

import json
from typing import cast
from uuid import UUID

import httpx
import pytest

from tests.integration.harness import IntegrationRuntime

pytestmark = pytest.mark.integration


def _chat_request(
    *,
    model: str = "e2e-model",
    streaming: bool = False,
) -> dict[str, object]:
    """Create an end-to-end chat request payload."""
    return {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "End-to-end secret prompt.",
            }
        ],
        "temperature": 0.25,
        "max_output_tokens": 32,
        "stream": streaming,
    }


def _parse_sse(body: str) -> list[tuple[str, dict[str, object]]]:
    """Parse normalized Trussium SSE events."""
    events: list[tuple[str, dict[str, object]]] = []

    for block in body.strip().split("\n\n"):
        lines = block.splitlines()
        event_name = lines[0].removeprefix("event: ")
        payload = cast(
            dict[str, object],
            json.loads(lines[1].removeprefix("data: ")),
        )
        events.append((event_name, payload))

    return events


def _assert_correlated_lifecycle(
    records: list[dict[str, object]],
    *,
    expected_events: list[str],
    request_id: str,
) -> None:
    """Assert exact lifecycle order and shared correlation metadata."""
    assert [record["event"] for record in records] == expected_events
    assert all(record["request_id"] == request_id for record in records)

    execution_ids = {record["execution_id"] for record in records}
    assert len(execution_ids) == 1
    execution_id = execution_ids.pop()
    assert isinstance(execution_id, str)
    assert str(UUID(execution_id)) == execution_id
    assert "End-to-end secret prompt." not in json.dumps(records)
    assert "e2e-test-api-key" not in json.dumps(records)


def test_runtime_health_over_real_network(
    integration_runtime: IntegrationRuntime,
) -> None:
    """Production liveness and readiness endpoints should serve real HTTP."""
    with httpx.Client(
        base_url=integration_runtime.base_url,
        timeout=5,
    ) as client:
        liveness = client.get(
            "/health/live",
            headers={"X-Request-ID": "e2e-health-live-57"},
        )
        readiness = client.get("/health/ready")

    assert liveness.status_code == 200
    assert liveness.json() == {"status": "ok"}
    assert liveness.headers["x-request-id"] == "e2e-health-live-57"
    assert readiness.status_code == 200
    assert readiness.json() == {"status": "ok"}
    assert str(UUID(readiness.headers["x-request-id"])) == readiness.headers["x-request-id"]


def test_non_streaming_completion_crosses_full_provider_path(
    integration_runtime: IntegrationRuntime,
) -> None:
    """A JSON completion should traverse runtime, SDK, and fake provider."""
    request_id = "e2e-json-completion-57"

    with httpx.Client(
        base_url=integration_runtime.base_url,
        timeout=5,
    ) as client:
        response = client.post(
            "/v1/chat/completions",
            headers={"X-Request-ID": request_id},
            json=_chat_request(),
        )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == request_id
    assert response.json() == {
        "id": "resp_e2e_json",
        "provider": "openai",
        "model": "e2e-model",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Hello from the end-to-end provider.",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "input_tokens": 3,
            "output_tokens": 5,
            "total_tokens": 8,
        },
    }

    provider_record = httpx.get(
        f"{integration_runtime.fake_openai_url}/recorded-request",
        timeout=5,
    ).json()["request"]
    assert provider_record["authorization"] == "Bearer e2e-test-api-key"
    provider_body = provider_record["body"]
    assert provider_body["model"] == "e2e-model"
    assert provider_body["input"] == [
        {
            "role": "user",
            "content": "End-to-end secret prompt.",
        }
    ]
    assert provider_body["temperature"] == 0.25
    assert provider_body["max_output_tokens"] == 32
    assert provider_body["store"] is False
    assert provider_body["stream"] is False

    records = integration_runtime.wait_for_terminal_log(
        request_id=request_id,
        event="http.request.completed",
    )
    _assert_correlated_lifecycle(
        records,
        expected_events=[
            "http.request.started",
            "capability.execution.started",
            "provider.execution.started",
            "provider.execution.completed",
            "capability.execution.completed",
            "http.request.completed",
        ],
        request_id=request_id,
    )
    assert records[-1]["http_status_code"] == 200


def test_streaming_completion_crosses_full_provider_path(
    integration_runtime: IntegrationRuntime,
) -> None:
    """OpenAI SDK stream events should become normalized SSE over real HTTP."""
    request_id = "e2e-stream-completion-57"

    with (
        httpx.Client(
            base_url=integration_runtime.base_url,
            timeout=5,
        ) as client,
        client.stream(
            "POST",
            "/v1/chat/completions",
            headers={"X-Request-ID": request_id},
            json=_chat_request(streaming=True),
        ) as response,
    ):
        body = "".join(response.iter_text())
        response_status = response.status_code
        response_request_id = response.headers["x-request-id"]

    assert response_status == 200
    assert response_request_id == request_id
    assert _parse_sse(body) == [
        (
            "start",
            {
                "type": "start",
                "id": "resp_e2e_stream",
                "provider": "openai",
                "model": "e2e-model",
            },
        ),
        (
            "delta",
            {
                "type": "delta",
                "id": "resp_e2e_stream",
                "content": "Hello from ",
            },
        ),
        (
            "delta",
            {
                "type": "delta",
                "id": "resp_e2e_stream",
                "content": "the integration stream.",
            },
        ),
        (
            "end",
            {
                "type": "end",
                "id": "resp_e2e_stream",
                "finish_reason": "stop",
                "usage": {
                    "input_tokens": 3,
                    "output_tokens": 5,
                    "total_tokens": 8,
                },
            },
        ),
    ]

    records = integration_runtime.wait_for_terminal_log(
        request_id=request_id,
        event="http.request.completed",
    )
    _assert_correlated_lifecycle(
        records,
        expected_events=[
            "http.request.started",
            "capability.execution.started",
            "provider.execution.started",
            "provider.execution.completed",
            "capability.execution.completed",
            "http.request.completed",
        ],
        request_id=request_id,
    )
    assert all(record.get("streaming") is True for record in records[1:-1])


def test_provider_rate_limit_is_normalized_end_to_end(
    integration_runtime: IntegrationRuntime,
) -> None:
    """An upstream 429 should cross the SDK and return a safe API envelope."""
    request_id = "e2e-rate-limit-57"

    with httpx.Client(
        base_url=integration_runtime.base_url,
        timeout=10,
    ) as client:
        response = client.post(
            "/v1/chat/completions",
            headers={"X-Request-ID": request_id},
            json=_chat_request(model="e2e-rate-limited"),
        )

    assert response.status_code == 429
    assert response.headers["x-request-id"] == request_id
    assert response.json() == {
        "detail": {
            "code": "openai_rate_limit_exceeded",
            "message": (
                "OpenAI temporarily rejected the request because a rate limit was exceeded."
            ),
        }
    }

    records = integration_runtime.wait_for_terminal_log(
        request_id=request_id,
        event="http.request.completed",
    )
    _assert_correlated_lifecycle(
        records,
        expected_events=[
            "http.request.started",
            "capability.execution.started",
            "provider.execution.started",
            "provider.execution.failed",
            "capability.execution.failed",
            "http.request.completed",
        ],
        request_id=request_id,
    )
    assert records[3]["error_code"] == "openai_rate_limit_exceeded"
    assert records[4]["error_code"] == "openai_rate_limit_exceeded"
    assert records[-1]["http_status_code"] == 429
