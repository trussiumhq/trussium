"""Application factory."""

from fastapi import FastAPI

from trussium.api import api_router
from trussium.capabilities.chat import ChatCapability
from trussium.config.settings import Settings, get_settings
from trussium.middleware import (
    RequestCorrelationMiddleware,
    RequestLoggingMiddleware,
)
from trussium.observability import (
    LoggingChatCapability,
    configure_logging,
)


def create_application(
    settings: Settings | None = None,
    *,
    chat_capability: ChatCapability | None = None,
) -> FastAPI:
    """Create and configure the Trussium application.

    Args:
        settings: Optional runtime settings override.
        chat_capability: Optional configured chat capability.

    Returns:
        Configured FastAPI application.
    """
    resolved_settings = settings or get_settings()

    configure_logging(
        debug=resolved_settings.runtime.debug,
    )

    application = FastAPI(
        title="Trussium",
        debug=resolved_settings.runtime.debug,
    )

    application.state.settings = resolved_settings
    application.state.chat_capability = (
        LoggingChatCapability(chat_capability)
        if chat_capability is not None
        and not isinstance(
            chat_capability,
            LoggingChatCapability,
        )
        else chat_capability
    )

    application.add_middleware(
        RequestLoggingMiddleware,
    )
    application.add_middleware(
        RequestCorrelationMiddleware,
    )

    application.include_router(api_router)

    return application
