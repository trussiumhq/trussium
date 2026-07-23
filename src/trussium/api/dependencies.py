"""Dependencies shared by Trussium API endpoints."""

from typing import cast

from fastapi import HTTPException, Request, status

from trussium.capabilities.chat import ChatCapability


def get_chat_capability(request: Request) -> ChatCapability:
    """Return the chat capability configured for the application.

    Args:
        request: Current FastAPI request.

    Returns:
        The configured chat capability.

    Raises:
        HTTPException: When no chat provider is configured.
    """
    capability = cast(
        ChatCapability | None,
        getattr(request.app.state, "chat_capability", None),
    )

    if capability is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "chat_capability_unavailable",
                "message": "No chat provider is configured.",
            },
        )

    return capability
