"""Deterministic local OpenAI Responses API used by integration tests."""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import cast

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, Response, StreamingResponse

app = FastAPI(title="Fake OpenAI Responses API")

_last_request: dict[str, object] | None = None
_recorded_provider_requests: list[dict[str, object]] = []
_recorded_trace_exports: list[dict[str, object]] = []
_reject_trace_exports = False
_control_events: dict[str, asyncio.Event] = {}
_control_states: dict[str, dict[str, bool]] = {}

_CONTROLLED_JSON_MODEL = "e2e-shutdown-json"
_CONTROLLED_STREAM_MODEL = "e2e-shutdown-stream"


def _control_event(model: str) -> asyncio.Event:
    """Return the release gate for a controlled provider workload."""
    return _control_events.setdefault(model, asyncio.Event())


def _control_state(model: str) -> dict[str, bool]:
    """Return observable lifecycle state for a controlled workload."""
    return _control_states.setdefault(
        model,
        {
            "active": False,
            "released": False,
            "completed": False,
            "finalized": False,
            "cancelled": False,
        },
    )


def _mark_control_state(model: str, key: str) -> None:
    """Mark one controlled-workload lifecycle transition."""
    _control_state(model)[key] = True


def _response_payload(
    *,
    response_id: str,
    model: str,
    text: str,
    status_value: str,
) -> dict[str, object]:
    """Build a minimal SDK-compatible OpenAI response payload."""
    return {
        "id": response_id,
        "created_at": 0.0,
        "model": model,
        "object": "response",
        "output": [
            {
                "id": f"msg_{response_id}",
                "content": [
                    {
                        "annotations": [],
                        "logprobs": [],
                        "text": text,
                        "type": "output_text",
                    }
                ],
                "role": "assistant",
                "status": "completed",
                "type": "message",
            }
        ],
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "tools": [],
        "status": status_value,
        "usage": {
            "input_tokens": 3,
            "input_tokens_details": {
                "cache_write_tokens": 0,
                "cached_tokens": 0,
            },
            "output_tokens": 5,
            "output_tokens_details": {
                "reasoning_tokens": 0,
            },
            "total_tokens": 8,
        },
    }


def _sse_event(
    event_name: str,
    payload: dict[str, object],
) -> str:
    """Encode one OpenAI-style server-sent event."""
    return f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"


@app.get("/health")
async def health() -> dict[str, str]:
    """Report fake-provider readiness."""
    return {"status": "ok"}


@app.get("/recorded-request")
async def recorded_request() -> dict[str, object | None]:
    """Return the most recent request observed by the fake provider."""
    return {"request": _last_request}


@app.get("/recorded-provider-requests")
async def recorded_provider_requests() -> dict[str, object]:
    """Return provider attempts observed during the integration session."""
    return {"requests": _recorded_provider_requests}


@app.get("/recorded-traces")
async def recorded_traces() -> dict[str, object]:
    """Return metadata for OTLP trace payloads received by the fake collector."""
    return {
        "count": len(_recorded_trace_exports),
        "exports": _recorded_trace_exports,
    }


@app.post("/v1/traces")
async def collect_traces(request: Request) -> Response:
    """Accept an OTLP HTTP/protobuf trace export without decoding user data."""
    body = await request.body()
    _recorded_trace_exports.append(
        {
            "content_type": request.headers.get("content-type"),
            "size": len(body),
        }
    )
    return Response(
        status_code=(
            status.HTTP_503_SERVICE_UNAVAILABLE if _reject_trace_exports else status.HTTP_200_OK
        )
    )


@app.post("/control/traces/{mode}")
async def control_trace_exports(mode: str) -> dict[str, bool]:
    """Enable or disable deterministic collector failure responses."""
    global _reject_trace_exports

    if mode not in {"accept", "reject"}:
        return {"rejecting": _reject_trace_exports}

    _reject_trace_exports = mode == "reject"
    return {"rejecting": _reject_trace_exports}


@app.get("/control/{model}")
async def controlled_workload_state(model: str) -> dict[str, object]:
    """Expose deterministic provider state to the process test harness."""
    return {
        "model": model,
        "state": _control_state(model),
    }


@app.post("/control/{model}/release")
async def release_controlled_workload(model: str) -> dict[str, object]:
    """Allow a controlled provider workload to finish successfully."""
    _mark_control_state(model, "released")
    _control_event(model).set()
    return {
        "model": model,
        "released": True,
    }


@app.post("/v1/responses", response_model=None)
async def create_response(request: Request) -> Response:
    """Return deterministic JSON, SSE, or rate-limit responses."""
    global _last_request

    body = cast(dict[str, object], await request.json())
    model = str(body.get("model", "e2e-model"))
    streaming = body.get("stream") is True
    _last_request = {
        "authorization": request.headers.get("authorization"),
        "baggage": request.headers.get("baggage"),
        "body": body,
        "request_id": request.headers.get("x-request-id"),
        "traceparent": request.headers.get("traceparent"),
        "tracestate": request.headers.get("tracestate"),
    }
    _recorded_provider_requests.append(_last_request)

    if model == "e2e-rate-limited":
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": {
                    "message": "Temporary test rate limit reached.",
                    "type": "rate_limit_error",
                    "param": None,
                    "code": "rate_limit_exceeded",
                }
            },
        )

    if model == _CONTROLLED_JSON_MODEL:
        _mark_control_state(model, "active")

        try:
            await _control_event(model).wait()
            _mark_control_state(model, "completed")
        except asyncio.CancelledError:
            _mark_control_state(model, "cancelled")
            raise
        finally:
            _mark_control_state(model, "finalized")

    if not streaming:
        return JSONResponse(
            content=_response_payload(
                response_id="resp_e2e_json",
                model=model,
                text="Hello from the end-to-end provider.",
                status_value="completed",
            )
        )

    async def stream_events() -> AsyncIterator[str]:
        response_id = "resp_e2e_stream"
        created_response = _response_payload(
            response_id=response_id,
            model=model,
            text="",
            status_value="in_progress",
        )
        completed_response = _response_payload(
            response_id=response_id,
            model=model,
            text="Hello from the integration stream.",
            status_value="completed",
        )

        controlled = model == _CONTROLLED_STREAM_MODEL

        try:
            if controlled:
                _mark_control_state(model, "active")

            yield _sse_event(
                "response.created",
                {
                    "type": "response.created",
                    "sequence_number": 0,
                    "response": created_response,
                },
            )

            if controlled:
                await _control_event(model).wait()

            yield _sse_event(
                "response.output_text.delta",
                {
                    "type": "response.output_text.delta",
                    "sequence_number": 1,
                    "item_id": f"msg_{response_id}",
                    "output_index": 0,
                    "content_index": 0,
                    "delta": "Hello from ",
                    "logprobs": [],
                },
            )
            yield _sse_event(
                "response.output_text.delta",
                {
                    "type": "response.output_text.delta",
                    "sequence_number": 2,
                    "item_id": f"msg_{response_id}",
                    "output_index": 0,
                    "content_index": 0,
                    "delta": "the integration stream.",
                    "logprobs": [],
                },
            )
            yield _sse_event(
                "response.completed",
                {
                    "type": "response.completed",
                    "sequence_number": 3,
                    "response": completed_response,
                },
            )
            yield "data: [DONE]\n\n"

            if controlled:
                _mark_control_state(model, "completed")
        except asyncio.CancelledError:
            if controlled:
                _mark_control_state(model, "cancelled")
            raise
        finally:
            if controlled:
                _mark_control_state(model, "finalized")

    return StreamingResponse(
        stream_events(),
        media_type="text/event-stream",
    )
