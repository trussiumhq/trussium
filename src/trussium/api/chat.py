"""Chat-completion API endpoints."""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from starlette.responses import Response

from trussium.api.dependencies import get_capability_execution_pipeline
from trussium.api.errors import capability_error_status_code
from trussium.api.sse import (
    ClosableStreamingResponse,
    stream_encoded_chat_events,
)
from trussium.capabilities.chat import (
    CHAT_CAPABILITY_NAME,
    ChatCapability,
    ChatCompletionRequest,
    ChatCompletionResponse,
)
from trussium.capabilities.errors import CapabilityExecutionError
from trussium.capabilities.execution import CapabilityExecutionPipeline
from trussium.capabilities.registry import (
    CapabilityContractMismatchError,
    CapabilityNotFoundError,
)
from trussium.config import resolve_model_alias
from trussium.providers import Provider, ProviderRouter

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
    http_request: Request,
    pipeline: Annotated[
        CapabilityExecutionPipeline,
        Depends(get_capability_execution_pipeline),
    ],
) -> Response:
    """Execute a normalized chat completion.

    Args:
        request: Normalized chat-completion request.
        pipeline: Application-owned provider-neutral execution pipeline.

    Returns:
        A normalized JSON response or an SSE streaming response.

    Raises:
        HTTPException: When non-streaming capability execution fails.
    """
    model = resolve_model_alias(
        request.model,
        getattr(http_request.app.state, "model_aliases", {}),
    )
    effective_request = request.model_copy(update={"model": model})

    if request.stream:
        try:
            events = pipeline.stream(
                CHAT_CAPABILITY_NAME,
                lambda capability: _require_chat_capability(capability).stream(effective_request),
                model=model,
            )
        except CapabilityNotFoundError as error:
            raise _chat_capability_unavailable() from error

        return ClosableStreamingResponse(
            content=stream_encoded_chat_events(events),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
            },
        )

    try:
        router = cast(
            ProviderRouter | None,
            getattr(http_request.app.state, "provider_router", None),
        )
        candidates = router.candidates(CHAT_CAPABILITY_NAME) if router is not None else ()
        if router is not None and candidates:
            completion = cast(
                ChatCompletionResponse,
                await router.execute_with_fallback(
                    CHAT_CAPABILITY_NAME,
                    lambda provider: _complete_provider(provider, effective_request),
                ),
            )
        else:
            completion = await pipeline.execute(
                CHAT_CAPABILITY_NAME,
                lambda capability: _require_chat_capability(capability).complete(effective_request),
                model=model,
            )
    except CapabilityNotFoundError as error:
        raise _chat_capability_unavailable() from error
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


def _require_chat_capability(capability: object) -> ChatCapability:
    """Return a validated chat contract from the generic execution boundary."""
    if not isinstance(capability, ChatCapability):
        raise CapabilityContractMismatchError(CHAT_CAPABILITY_NAME)

    return capability


async def _complete_provider(
    provider: Provider, request: ChatCompletionRequest
) -> ChatCompletionResponse:
    """Complete a request using the provider's registered chat capability."""
    for capability in provider.capabilities:
        if isinstance(capability, ChatCapability):
            return await capability.complete(request)
    raise CapabilityContractMismatchError(CHAT_CAPABILITY_NAME)


def _chat_capability_unavailable() -> HTTPException:
    """Create the stable missing-chat HTTP failure."""
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "chat_capability_unavailable",
            "message": "No chat provider is configured.",
        },
    )
