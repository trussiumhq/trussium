from typing import cast

from fastapi import FastAPI

from trussium.app import create_application
from trussium.capabilities.chat import ChatCapability
from trussium.config.settings import Settings
from trussium.observability import LoggingChatCapability


def test_create_application_returns_fastapi() -> None:
    app = create_application()

    assert isinstance(app, FastAPI)


def test_application_contains_settings() -> None:
    app = create_application()

    assert isinstance(app.state.settings, Settings)


def test_application_debug_matches_settings() -> None:
    settings = Settings()

    app = create_application(settings)

    assert app.debug is settings.runtime.debug


def test_application_title() -> None:
    app = create_application()

    assert app.title == "Trussium"


def test_application_wraps_configured_chat_capability_with_logging() -> None:
    capability = cast(
        ChatCapability,
        object(),
    )

    app = create_application(
        chat_capability=capability,
    )

    assert isinstance(
        app.state.chat_capability,
        LoggingChatCapability,
    )


def test_application_does_not_wrap_logging_capability_twice() -> None:
    capability = cast(
        ChatCapability,
        object(),
    )
    logging_capability = LoggingChatCapability(capability)

    app = create_application(
        chat_capability=logging_capability,
    )

    assert app.state.chat_capability is logging_capability
