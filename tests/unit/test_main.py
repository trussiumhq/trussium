from typing import cast

import pytest
from fastapi import FastAPI

from trussium import __main__
from trussium.capabilities.chat import ChatCapability
from trussium.config.settings import RuntimeSettings, Settings


def test_main_module_exists() -> None:
    assert callable(__main__.main)


def test_main_configures_bounded_graceful_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The production server should receive Trussium's shutdown deadline."""
    settings = Settings(
        runtime=RuntimeSettings(
            host="127.0.0.1",
            port=9017,
            graceful_shutdown_seconds=9,
        )
    )
    capability = cast(ChatCapability, object())
    application = FastAPI()
    observed: dict[str, object] = {}

    class FakeServer:
        """Record production server execution."""

        def run(self) -> None:
            observed["ran"] = True

    def create_capability(**_: object) -> ChatCapability:
        return capability

    def create_app(**_: object) -> FastAPI:
        return application

    def configure_server(
        app: FastAPI,
        *,
        settings: RuntimeSettings,
    ) -> FakeServer:
        observed.update(
            {
                "app": app,
                "settings": settings,
            }
        )
        return FakeServer()

    monkeypatch.setattr(__main__, "get_settings", lambda: settings)
    monkeypatch.setattr(
        __main__,
        "create_chat_capability_from_environment",
        create_capability,
    )
    monkeypatch.setattr(__main__, "create_application", create_app)
    monkeypatch.setattr(__main__, "create_server", configure_server)

    __main__.main()

    assert observed == {
        "app": application,
        "settings": settings.runtime,
        "ran": True,
    }
