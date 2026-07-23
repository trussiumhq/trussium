"""Chat-completion API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from trussium.api.dependencies import get_chat_capability
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
)
async def create_chat_completion(
    request: ChatCompletionRequest,
    capability: Annotated[
        ChatCapability,
        Depends(get_chat_capability),
    ],
) -> ChatCompletionResponse:
    """Execute a normalized non-streaming chat completion.

    Args:
        request: Normalized chat-completion request.
        capability: Configured provider-neutral chat capability.

    Returns:
        A normalized chat-completion response.

    Raises:
        HTTPException: When streaming is requested before the streaming
            transport is implemented.
    """
    if request.stream:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail={
                "code": "streaming_not_implemented",
                "message": (
                    "HTTP streaming is not implemented yet. Submit the request with stream=false."
                ),
            },
        )

    return await capability.complete(request)
