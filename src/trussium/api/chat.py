"""Chat-completion API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.responses import Response

from trussium.api.dependencies import get_chat_capability
from trussium.api.errors import capability_error_status_code
from trussium.api.sse import (
    ClosableStreamingResponse,
    stream_chat_events,
)
from trussium.capabilities.chat import (
    ChatCapability,
    ChatCompletionRequest,
    ChatCompletionResponse,
)
from trussium.capabilities.errors import CapabilityExecutionError

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
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "The provider rejected the request.",
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "description": "The provider rate limit was exceeded.",
        },
        status.HTTP_502_BAD_GATEWAY: {
            "description": ("The configured provider could not serve the request."),
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": ("The configured provider is temporarily unavailable."),
        },
        status.HTTP_504_GATEWAY_TIMEOUT: {
            "description": "The configured provider request timed out.",
        },
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

    Raises:
        HTTPException: When non-streaming capability execution fails.
    """
    if request.stream:
        return ClosableStreamingResponse(
            content=stream_chat_events(
                capability=capability,
                request=request,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
            },
        )

    try:
        completion = await capability.complete(request)
    except CapabilityExecutionError as error:
        raise HTTPException(
            status_code=capability_error_status_code(error.category),
            detail={
                "code": error.code,
                "message": error.message,
            },
        ) from error

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=completion.model_dump(mode="json"),
    )
