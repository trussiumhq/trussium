import io
import json
from typing import cast

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from trussium import __main__
from trussium.capabilities import CHAT_CAPABILITY_NAME, CapabilityRegistry
from trussium.capabilities.chat import ChatCapability
from trussium.config.settings import RuntimeSettings, Settings
from trussium.observability import RuntimeTracing, configure_logging


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
    health_check = object()
    application = FastAPI()
    observed: dict[str, object] = {}

    class FakeServer:
        """Record production server execution."""

        def run(self) -> None:
            observed["ran"] = True

    def create_capability(**_: object) -> ChatCapability:
        observed["capability_arguments"] = _
        return capability

    def create_health_check(**_: object) -> object:
        observed["health_check_arguments"] = _
        return health_check

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
    monkeypatch.setattr(
        __main__,
        "create_provider_health_check_from_environment",
        create_health_check,
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
    health_check_arguments = cast(
        dict[str, object],
        observed.pop("health_check_arguments"),
    )
    tracing = application_arguments["tracing"]

    assert isinstance(tracing, RuntimeTracing)
    assert capability_arguments["provider"] is settings.provider
    assert capability_arguments["timeouts"] is settings.timeouts
    assert capability_arguments["tracer"] is tracing.tracer
    assert health_check_arguments == {
        "provider": settings.provider,
        "readiness": settings.readiness,
    }
    assert application_arguments["settings"] is settings
    capability_registry = application_arguments["capability_registry"]
    assert isinstance(capability_registry, CapabilityRegistry)
    assert capability_registry.sealed is False
    assert capability_registry.names == (CHAT_CAPABILITY_NAME,)
    assert capability_registry.get(CHAT_CAPABILITY_NAME) is capability
    assert "chat_capability" not in application_arguments
    assert application_arguments["dependency_health_check"] is health_check

    assert observed == {
        "app": application,
        "settings": settings.runtime,
        "ran": True,
    }


def test_main_logs_invalid_configuration_without_input_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Early settings failures should be structured without leaking rejected input."""
    output = io.StringIO()

    with pytest.raises(ValidationError) as validation:
        Settings.model_validate(
            {
                "runtime": {
                    "port": "secret-invalid-port",
                }
            }
        )

    def configure_test_logging(**_: object) -> None:
        configure_logging(stream=output)

    def raise_validation_error() -> Settings:
        raise validation.value

    monkeypatch.setattr(__main__, "configure_logging", configure_test_logging)
    monkeypatch.setattr(__main__, "get_settings", raise_validation_error)

    with pytest.raises(SystemExit) as exit_status:
        __main__.main()

    assert exit_status.value.code == 2
    payload = json.loads(output.getvalue())
    assert payload["event"] == "runtime.configuration.invalid"
    assert payload["error_code"] == "invalid_configuration"
    assert payload["error_count"] == 1
    assert payload["error_type"] == "ValidationError"
    assert "secret-invalid-port" not in output.getvalue()
