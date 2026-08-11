from typing import cast

import pytest
from fastapi import FastAPI

from trussium import __main__
from trussium.capabilities.chat import ChatCapability
from trussium.config.settings import RuntimeSettings, Settings
from trussium.observability import RuntimeTracing


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
        observed["capability_arguments"] = _
        return capability

    def create_app(**_: object) -> FastAPI:
        observed["application_arguments"] = _
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

    capability_arguments = cast(
        dict[str, object],
        observed.pop("capability_arguments"),
    )
    application_arguments = cast(
        dict[str, object],
        observed.pop("application_arguments"),
    )
    tracing = application_arguments["tracing"]

    assert isinstance(tracing, RuntimeTracing)
    assert capability_arguments["provider"] is settings.provider
    assert capability_arguments["timeouts"] is settings.timeouts
    assert capability_arguments["tracer"] is tracing.tracer
    assert application_arguments["settings"] is settings
    assert application_arguments["chat_capability"] is capability

    assert observed == {
        "app": application,
        "settings": settings.runtime,
        "ran": True,
    }
