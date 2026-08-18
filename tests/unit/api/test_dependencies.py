"""Tests for application capability dependency resolution."""

from typing import cast
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException, Request, status

from trussium.api.dependencies import (
    get_capability_execution_pipeline,
    get_chat_capability,
)
from trussium.capabilities import (
    CHAT_CAPABILITY_NAME,
    CapabilityContractMismatchError,
    CapabilityExecutionPipeline,
    CapabilityRegistry,
)
from trussium.capabilities.chat import ChatCapability


def create_request(application: FastAPI) -> Request:
    """Create a minimal HTTP request bound to the supplied application."""
    return Request(
        {
            "type": "http",
            "app": application,
            "method": "GET",
            "path": "/",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "scheme": "http",
            "root_path": "",
            "http_version": "1.1",
        }
    )


def test_registry_is_the_authoritative_chat_lookup() -> None:
    """A configured registry should take precedence over the compatibility alias."""
    registered = cast(ChatCapability, MagicMock(spec=ChatCapability))
    legacy = cast(ChatCapability, MagicMock(spec=ChatCapability))
    registry = CapabilityRegistry()
    registry.register(CHAT_CAPABILITY_NAME, registered)
    registry.seal()
    application = FastAPI()
    application.state.capability_registry = registry
    application.state.chat_capability = legacy

    resolved = get_chat_capability(create_request(application))

    assert resolved is registered


def test_application_execution_pipeline_dependency_preserves_identity() -> None:
    """API execution should use the exact application-owned pipeline."""
    registry = CapabilityRegistry()
    registry.seal()
    pipeline = CapabilityExecutionPipeline(registry)
    application = FastAPI()
    application.state.capability_execution_pipeline = pipeline

    resolved = get_capability_execution_pipeline(create_request(application))

    assert resolved is pipeline


def test_missing_application_execution_pipeline_fails_as_composition_error() -> None:
    """An externally assembled API must explicitly provide its execution boundary."""
    application = FastAPI()

    with pytest.raises(RuntimeError, match="pipeline is not configured"):
        get_capability_execution_pipeline(create_request(application))


def test_legacy_application_state_remains_a_compatibility_fallback() -> None:
    """Externally constructed applications without a registry should keep working."""
    capability = cast(ChatCapability, MagicMock(spec=ChatCapability))
    application = FastAPI()
    application.state.chat_capability = capability

    resolved = get_chat_capability(create_request(application))

    assert resolved is capability


def test_empty_registry_retains_the_bounded_unavailable_response() -> None:
    """An authoritative empty registry should not fall through to direct state."""
    registry = CapabilityRegistry()
    registry.seal()
    application = FastAPI()
    application.state.capability_registry = registry
    application.state.chat_capability = cast(
        ChatCapability,
        MagicMock(spec=ChatCapability),
    )

    with pytest.raises(HTTPException) as captured:
        get_chat_capability(create_request(application))

    assert captured.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    detail = cast(dict[str, str], captured.value.detail)
    assert detail == {
        "code": "chat_capability_unavailable",
        "message": "No chat provider is configured.",
    }


def test_external_registry_contract_mismatch_is_typed() -> None:
    """Bypassed application composition should still fail with a bounded error."""
    registry = CapabilityRegistry()
    registry.register(CHAT_CAPABILITY_NAME, object())
    registry.seal()
    application = FastAPI()
    application.state.capability_registry = registry

    with pytest.raises(CapabilityContractMismatchError) as captured:
        get_chat_capability(create_request(application))

    assert captured.value.capability_name == CHAT_CAPABILITY_NAME
