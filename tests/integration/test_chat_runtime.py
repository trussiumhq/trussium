"""End-to-end tests for Trussium's first chat vertical slice."""

import json
from time import sleep
from typing import cast
from uuid import UUID

import httpx
import pytest

from tests.integration.harness import IntegrationRuntime

pytestmark = pytest.mark.integration

_INBOUND_TRACE_ID = "0af7651916cd43dd8448eb211c80319c"
_INBOUND_PARENT_SPAN_ID = "b7ad6b7169203331"
_INBOUND_TRACEPARENT = f"00-{_INBOUND_TRACE_ID}-{_INBOUND_PARENT_SPAN_ID}-01"


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

    trace_ids = {record["trace_id"] for record in records}
    assert len(trace_ids) == 1
    trace_id = trace_ids.pop()
    assert isinstance(trace_id, str)
    assert len(trace_id) == 32
    assert all(len(str(record["span_id"])) == 16 for record in records)
    assert "End-to-end secret prompt." not in json.dumps(records)
    assert "e2e-test-api-key" not in json.dumps(records)


def _assert_outbound_trace_context(
    provider_record: dict[str, object],
    records: list[dict[str, object]],
    *,
    expected_tracestate: str | None = None,
) -> None:
    """Assert the provider received the active Trussium CLIENT span."""
    traceparent = provider_record["traceparent"]
    assert isinstance(traceparent, str)
    version, trace_id, parent_span_id, trace_flags = traceparent.split("-")
    provider_started = next(
        record for record in records if record["event"] == "provider.execution.started"
    )

    assert version == "00"
    assert trace_id == records[0]["trace_id"]
    assert parent_span_id == provider_started["span_id"]
    assert int(trace_flags, 16) & 0x01 == 0x01
    assert provider_record["tracestate"] == expected_tracestate
    assert provider_record["baggage"] is None
    assert provider_record["request_id"] is None


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
        components = client.get("/health/components")
        availability = client.get("/v1/capabilities/availability")
        metrics = client.get("/metrics")

    assert liveness.status_code == 200
    assert liveness.json() == {"status": "ok"}
    assert liveness.headers["x-request-id"] == "e2e-health-live-57"
    assert readiness.status_code == 200
    assert readiness.json() == {
        "status": "ok",
        "dependencies": [
            {
                "name": "provider",
                "status": "ok",
                "provider": "openai",
                "model": "e2e-model",
            }
        ],
    }
    assert str(UUID(readiness.headers["x-request-id"])) == readiness.headers["x-request-id"]
    assert components.status_code == 200
    assert components.json() == {"status": "ok", "components": []}
    assert str(UUID(components.headers["x-request-id"])) == components.headers["x-request-id"]
    assert availability.status_code == 200
    assert availability.json() == {
        "status": "available",
        "capabilities": [
            {"name": "chat.completions", "status": "available"},
            {"name": "embeddings", "status": "available"},
        ],
    }
    assert str(UUID(availability.headers["x-request-id"])) == availability.headers["x-request-id"]
    assert metrics.status_code == 200
    assert metrics.headers["content-type"].startswith("text/plain")
    assert "python_info" in metrics.text
    assert "trussium_http_requests_active 0.0" in metrics.text

    operational_events = [record["event"] for record in integration_runtime.operational_logs()]
    assert operational_events[:5] == [
        "runtime.configuration.loaded",
        "provider.configuration.ready",
        "readiness.configuration.loaded",
        "observability.configuration.loaded",
        "runtime.started",
    ]
    runtime_configuration = integration_runtime.operational_logs(
        event="runtime.configuration.loaded"
    )[0]
    assert isinstance(runtime_configuration["port"], int)
    assert runtime_configuration["port"] > 0
    assert runtime_configuration["graceful_shutdown_seconds"] == 30
    provider_configuration = integration_runtime.operational_logs(
        event="provider.configuration.ready"
    )[0]
    assert provider_configuration["provider"] == "openai"
    assert provider_configuration["provider_configured"] is True
    serialized = json.dumps(integration_runtime.operational_logs())
    assert "e2e-test-api-key" not in serialized
    assert integration_runtime.fake_openai_url not in serialized


def test_dependency_readiness_fails_and_recovers_over_real_sdk_path(
    integration_runtime: IntegrationRuntime,
) -> None:
    """Production readiness should track required-model metadata availability."""
    with httpx.Client(timeout=2) as client:
        control = client.post(f"{integration_runtime.fake_openai_url}/control/model-health/missing")
        control.raise_for_status()
        sleep(0.12)

        unavailable = client.get(f"{integration_runtime.base_url}/health/ready")

        control = client.post(
            f"{integration_runtime.fake_openai_url}/control/model-health/available"
        )
        control.raise_for_status()
        sleep(0.12)

        recovered = client.get(f"{integration_runtime.base_url}/health/ready")

    assert unavailable.status_code == 503
    assert unavailable.json() == {
        "status": "unavailable",
        "dependencies": [
            {
                "name": "provider",
                "status": "unavailable",
                "provider": "openai",
                "model": "e2e-model",
                "reason": "model_unavailable",
            }
        ],
    }
    assert recovered.status_code == 200
    assert recovered.json()["status"] == "ok"

    unavailable_log = integration_runtime.wait_for_operational_log(
        event="readiness.dependency.unavailable"
    )
    recovered_log = integration_runtime.wait_for_operational_log(event="readiness.dependency.ok")
    assert unavailable_log["error_code"] == "model_unavailable"
    assert recovered_log["outcome"] == "ok"
    serialized = json.dumps([unavailable_log, recovered_log])
    assert "e2e-test-api-key" not in serialized
    assert integration_runtime.fake_openai_url not in serialized


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
            headers={
                "X-Request-ID": request_id,
                "baggage": "private-user-data=must-not-leave-runtime",
                "traceparent": _INBOUND_TRACEPARENT,
                "tracestate": "vendor=opaque-value",
            },
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
    assert records[0]["trace_id"] == _INBOUND_TRACE_ID
    _assert_outbound_trace_context(
        provider_record,
        records,
        expected_tracestate="vendor=opaque-value",
    )
    assert "must-not-leave-runtime" not in json.dumps(provider_record)

    trace_exports = integration_runtime.wait_for_trace_exports(
        minimum_count=1,
    )
    assert any(
        trace_export["content_type"] == "application/x-protobuf"
        and isinstance(trace_export["size"], int)
        and trace_export["size"] > 0
        for trace_export in trace_exports
    )


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

    provider_record = httpx.get(
        f"{integration_runtime.fake_openai_url}/recorded-request",
        timeout=5,
    ).json()["request"]
    _assert_outbound_trace_context(provider_record, records)


def test_trace_export_failure_is_reported_without_collector_details(
    integration_runtime: IntegrationRuntime,
) -> None:
    """A real exporter failure should produce the bounded operational event."""
    control_url = f"{integration_runtime.fake_openai_url}/control/traces"
    httpx.post(f"{control_url}/reject", timeout=5).raise_for_status()

    try:
        response = httpx.post(
            f"{integration_runtime.base_url}/v1/chat/completions",
            headers={"X-Request-ID": "e2e-trace-export-failure-83"},
            json=_chat_request(model="e2e-trace-export-failure"),
            timeout=5,
        )
        assert response.status_code == 200

        failure = integration_runtime.wait_for_operational_log(
            event="observability.trace_export.failed"
        )
    finally:
        httpx.post(f"{control_url}/accept", timeout=5).raise_for_status()

    assert failure["level"] == "ERROR"
    assert failure["error_code"] == "trace_export_failed"
    assert isinstance(failure["span_count"], int)
    assert failure["span_count"] > 0
    serialized = json.dumps(failure)
    assert integration_runtime.fake_openai_url not in serialized
    assert "e2e-test-api-key" not in serialized
    assert "exception" not in failure


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

    provider_attempts = httpx.get(
        f"{integration_runtime.fake_openai_url}/recorded-provider-requests",
        timeout=5,
    ).json()["requests"]
    rate_limit_attempts = [
        attempt for attempt in provider_attempts if attempt["body"]["model"] == "e2e-rate-limited"
    ]
    assert len(rate_limit_attempts) > 1
    assert len({attempt["traceparent"] for attempt in rate_limit_attempts}) == 1
    _assert_outbound_trace_context(rate_limit_attempts[-1], records)
