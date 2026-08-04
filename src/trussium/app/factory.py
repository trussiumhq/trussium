"""Application factory."""

from fastapi import FastAPI

from trussium.api import api_router
from trussium.capabilities.chat import ChatCapability
from trussium.config.settings import Settings, get_settings
from trussium.middleware import RequestCorrelationMiddleware


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

    application = FastAPI(
        title="Trussium",
        debug=resolved_settings.runtime.debug,
    )

    application.state.settings = resolved_settings
    application.state.chat_capability = chat_capability

    application.add_middleware(
        RequestCorrelationMiddleware,
    )

    application.include_router(api_router)

    return application
