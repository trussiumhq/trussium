"""Public runtime exception hierarchy contracts."""

import asyncio

import pytest

import trussium
from trussium.capabilities.errors import (
    CapabilityErrorCategory,
    CapabilityExecutionError,
)
from trussium.errors import (
    CapabilityError,
    ConfigurationError,
    DependencyError,
    LifecycleError,
    ProviderError,
    RuntimeExecutionError,
    TrussiumError,
)
from trussium.providers.openai import OpenAIProviderError


@pytest.mark.parametrize(
    ("error_type", "default_code"),
    [
        (TrussiumError, "trussium_error"),
        (ConfigurationError, "configuration_error"),
        (RuntimeExecutionError, "runtime_execution_error"),
        (LifecycleError, "lifecycle_error"),
        (DependencyError, "dependency_error"),
        (CapabilityError, "capability_error"),
        (ProviderError, "provider_error"),
    ],
)
def test_domain_errors_have_stable_defaults(
    error_type: type[TrussiumError],
    default_code: str,
) -> None:
    error = error_type("Safe failure")

    assert isinstance(error, RuntimeError)
    assert error.code == default_code
    assert error.message == "Safe failure"
    assert str(error) == "Safe failure"


def test_runtime_hierarchy_exposes_intended_catch_boundaries() -> None:
    provider_error = ProviderError("Provider failure")

    assert isinstance(provider_error, CapabilityError)
    assert isinstance(provider_error, RuntimeExecutionError)
    assert isinstance(provider_error, TrussiumError)
    assert not isinstance(ConfigurationError("Invalid configuration"), RuntimeExecutionError)


def test_specific_code_overrides_domain_default() -> None:
    error = DependencyError("Dependency unavailable", code="dependency_unavailable")

    assert error.code == "dependency_unavailable"


@pytest.mark.parametrize(("code", "message"), [("", "Safe"), ("   ", "Safe"), (None, "")])
def test_public_error_attributes_must_not_be_empty(
    code: str | None,
    message: str,
) -> None:
    with pytest.raises(ValueError):
        TrussiumError(message, code=code)


def test_capability_execution_error_remains_compatible() -> None:
    error = CapabilityExecutionError(
        code="provider_timeout",
        message="The provider timed out.",
        category=CapabilityErrorCategory.UPSTREAM_TIMEOUT,
    )

    assert isinstance(error, CapabilityError)
    assert isinstance(error, RuntimeExecutionError)
    assert isinstance(error, RuntimeError)
    assert error.code == "provider_timeout"
    assert error.message == "The provider timed out."
    assert error.category is CapabilityErrorCategory.UPSTREAM_TIMEOUT
    assert str(error) == "The provider timed out."


def test_openai_provider_error_remains_compatible() -> None:
    error = OpenAIProviderError("OpenAI response could not be normalized")

    assert isinstance(error, ProviderError)
    assert isinstance(error, CapabilityError)
    assert isinstance(error, RuntimeError)
    assert error.code == "provider_error"
    assert error.message == "OpenAI response could not be normalized"
    assert str(error) == "OpenAI response could not be normalized"


def test_top_level_package_exports_public_hierarchy() -> None:
    assert trussium.TrussiumError is TrussiumError
    assert trussium.ConfigurationError is ConfigurationError
    assert trussium.RuntimeExecutionError is RuntimeExecutionError
    assert trussium.LifecycleError is LifecycleError
    assert trussium.DependencyError is DependencyError
    assert trussium.CapabilityError is CapabilityError
    assert trussium.ProviderError is ProviderError


def test_cancellation_is_not_reclassified() -> None:
    assert not isinstance(asyncio.CancelledError(), TrussiumError)
