import io
import json
from typing import cast
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from trussium.app import create_application
from trussium.capabilities.chat import ChatCapability
from trussium.config.settings import Settings
from trussium.observability import (
    LoggingChatCapability,
    RuntimeTracing,
    configure_logging,
)


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


def test_application_lifespan_emits_ordered_operational_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Application startup and shutdown should expose the stable event contract."""
    output = io.StringIO()

    def configure_test_logging(**_: object) -> None:
        configure_logging(stream=output)

    monkeypatch.setattr(
        "trussium.app.factory.configure_logging",
        configure_test_logging,
    )
    app = create_application(Settings())

    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200

    payloads = [json.loads(line) for line in output.getvalue().splitlines()]
    events = [payload.get("event") for payload in payloads]
    lifecycle_events = [
        event
        for event in events
        if event
        in {
            "runtime.configuration.loaded",
            "provider.configuration.unavailable",
            "observability.configuration.loaded",
            "runtime.started",
            "runtime.stopping",
            "observability.tracing.shutdown.completed",
            "runtime.stopped",
        }
    ]

    assert lifecycle_events == [
        "runtime.configuration.loaded",
        "provider.configuration.unavailable",
        "observability.configuration.loaded",
        "runtime.started",
        "runtime.stopping",
        "observability.tracing.shutdown.completed",
        "runtime.stopped",
    ]
    stopped = next(payload for payload in payloads if payload.get("event") == "runtime.stopped")
    assert stopped["outcome"] == "completed"
    assert isinstance(stopped["duration_ms"], float)


def test_tracing_shutdown_failure_is_bounded_and_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A shutdown exception should be logged safely and still reach the caller."""
    output = io.StringIO()

    def configure_test_logging(**_: object) -> None:
        configure_logging(stream=output)

    tracing = MagicMock(spec=RuntimeTracing)
    tracing.enabled = False
    tracing.shutdown.side_effect = RuntimeError("secret shutdown detail")
    monkeypatch.setattr(
        "trussium.app.factory.configure_logging",
        configure_test_logging,
    )
    app = create_application(
        Settings(),
        tracing=cast(RuntimeTracing, tracing),
    )

    with pytest.raises(RuntimeError, match="secret shutdown detail"), TestClient(app) as client:
        assert client.get("/health/live").status_code == 200

    payloads = [json.loads(line) for line in output.getvalue().splitlines()]
    failure = next(
        payload
        for payload in payloads
        if payload.get("event") == "observability.tracing.shutdown.failed"
    )
    stopped = next(payload for payload in payloads if payload.get("event") == "runtime.stopped")
    assert failure["error_code"] == "tracing_shutdown_failed"
    assert failure["error_type"] == "RuntimeError"
    assert "exception" not in failure
    assert stopped["outcome"] == "failed"
    assert "secret shutdown detail" not in output.getvalue()
