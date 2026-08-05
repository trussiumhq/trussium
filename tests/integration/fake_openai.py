"""Deterministic local OpenAI Responses API used by integration tests."""

import json
from collections.abc import AsyncIterator
from typing import cast

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, Response, StreamingResponse

app = FastAPI(title="Fake OpenAI Responses API")

_last_request: dict[str, object] | None = None


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


@app.post("/v1/responses", response_model=None)
async def create_response(request: Request) -> Response:
    """Return deterministic JSON, SSE, or rate-limit responses."""
    global _last_request

    body = cast(dict[str, object], await request.json())
    model = str(body.get("model", "e2e-model"))
    streaming = body.get("stream") is True
    _last_request = {
        "authorization": request.headers.get("authorization"),
        "body": body,
    }

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

        yield _sse_event(
            "response.created",
            {
                "type": "response.created",
                "sequence_number": 0,
                "response": created_response,
            },
        )
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

    return StreamingResponse(
        stream_events(),
        media_type="text/event-stream",
    )
