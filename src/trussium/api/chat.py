"""Chat-completion API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.responses import Response

from trussium.api.dependencies import get_chat_capability
from trussium.api.sse import stream_chat_events
from trussium.capabilities.chat import (
    ChatCapability,
    ChatCompletionRequest,
    ChatCompletionResponse,
)

router = APIRouter(
    prefix="/v1/chat",
    tags=["chat"],
)


@router.post(
    "/completions",
    response_model=ChatCompletionResponse,
    status_code=status.HTTP_200_OK,
    summary="Create a chat completion",
    responses={
        status.HTTP_200_OK: {
            "description": ("A normalized JSON completion or a server-sent event stream."),
            "content": {
                "application/json": {
                    "schema": {
                        "$ref": ("#/components/schemas/ChatCompletionResponse"),
                    }
                },
                "text/event-stream": {
                    "schema": {
                        "type": "string",
                    }
                },
            },
        }
    },
)
async def create_chat_completion(
    request: ChatCompletionRequest,
    capability: Annotated[
        ChatCapability,
        Depends(get_chat_capability),
    ],
) -> Response:
    """Execute a normalized chat completion.

    Args:
        request: Normalized chat-completion request.
        capability: Configured provider-neutral chat capability.

    Returns:
        A normalized JSON response or an SSE streaming response.
    """
    if request.stream:
        return StreamingResponse(
            content=stream_chat_events(
                capability=capability,
                request=request,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
            },
        )

    completion = await capability.complete(request)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=completion.model_dump(mode="json"),
    )
