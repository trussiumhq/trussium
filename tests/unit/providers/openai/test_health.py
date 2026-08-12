"""Tests for OpenAI-compatible provider dependency health checking."""

import asyncio
from dataclasses import dataclass
from typing import cast

import httpx
import pytest

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
)
from trussium.providers.openai import OpenAICompatibleProviderHealthCheck
from trussium.runtime import (
    DependencyFailureReason,
    DependencyHealth,
    DependencyStatus,
)


class FakeModels:
    """Fake SDK models resource with configurable outcomes."""

    def __init__(self, error: Exception | None = None) -> None:
        """Initialize the resource outcome."""
        self.error = error
        self.list_calls = 0
        self.retrieved_models: list[str] = []

    async def list(self) -> object:
        """Return model-list success or the configured failure."""
        self.list_calls += 1

        if self.error is not None:
            raise self.error

        return object()

    async def retrieve(self, model: str) -> object:
        """Return model-retrieval success or the configured failure."""
        self.retrieved_models.append(model)

        if self.error is not None:
            raise self.error

        return object()


@dataclass
class FakeClient:
    """Minimal client surface owned by the provider check."""

    models: FakeModels
    closed: bool = False

    async def close(self) -> None:
        """Record client resource cleanup."""
        self.closed = True


def create_check(
    *,
    error: Exception | None = None,
    model: str | None = None,
) -> tuple[OpenAICompatibleProviderHealthCheck, FakeClient]:
    """Create a check around a structurally compatible fake SDK client."""
    client = FakeClient(models=FakeModels(error))
    check = OpenAICompatibleProviderHealthCheck(
        cast(AsyncOpenAI, client),
        provider="openai",
        model=model,
    )
    return check, client


def status_error(error_type: type[APIStatusError], status_code: int) -> APIStatusError:
    """Create one SDK status error without external requests."""
    request = httpx.Request("GET", "https://private-provider.example/v1/models")
    response = httpx.Response(status_code, request=request)
    return error_type("private provider response", response=response, body={})


def test_provider_check_lists_models_without_required_model_and_closes() -> None:
    """Provider-only readiness should validate metadata access, not inference."""
    check, client = create_check()

    result = asyncio.run(check.check())
    asyncio.run(check.close())

    assert result == DependencyHealth(
        name="provider",
        status=DependencyStatus.OK,
        provider="openai",
    )
    assert client.models.list_calls == 1
    assert client.models.retrieved_models == []
    assert client.closed is True


def test_provider_check_retrieves_only_the_required_model() -> None:
    """Model-aware readiness should use metadata retrieval without inference."""
    check, client = create_check(model="required-model")

    result = asyncio.run(check.check())

    assert result.status is DependencyStatus.OK
    assert result.model == "required-model"
    assert client.models.list_calls == 0
    assert client.models.retrieved_models == ["required-model"]


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            status_error(AuthenticationError, 401),
            DependencyFailureReason.PROVIDER_AUTHENTICATION_FAILED,
        ),
        (
            status_error(PermissionDeniedError, 403),
            DependencyFailureReason.PROVIDER_PERMISSION_DENIED,
        ),
        (
            status_error(RateLimitError, 429),
            DependencyFailureReason.PROVIDER_RATE_LIMITED,
        ),
        (
            APITimeoutError(
                request=httpx.Request("GET", "https://private-provider.example/v1/models")
            ),
            DependencyFailureReason.PROVIDER_TIMEOUT,
        ),
        (
            APIConnectionError(
                request=httpx.Request("GET", "https://private-provider.example/v1/models")
            ),
            DependencyFailureReason.PROVIDER_UNREACHABLE,
        ),
        (
            APIError(
                "private response body",
                request=httpx.Request("GET", "https://private-provider.example/v1/models"),
                body=None,
            ),
            DependencyFailureReason.PROVIDER_CHECK_FAILED,
        ),
    ],
)
def test_provider_failures_normalize_to_stable_reasons(
    error: Exception,
    expected: DependencyFailureReason,
) -> None:
    """SDK details should collapse into the bounded provider-neutral contract."""
    check, _ = create_check(error=error)

    result = asyncio.run(check.check())

    assert result.status is DependencyStatus.UNAVAILABLE
    assert result.reason is expected


def test_not_found_is_model_specific_only_when_model_is_required() -> None:
    """A missing configured model should remain distinct from endpoint failure."""
    error = status_error(NotFoundError, 404)
    model_check, _ = create_check(error=error, model="missing-model")
    provider_check, _ = create_check(error=error)

    model_result = asyncio.run(model_check.check())
    provider_result = asyncio.run(provider_check.check())

    assert model_result.reason is DependencyFailureReason.MODEL_UNAVAILABLE
    assert provider_result.reason is DependencyFailureReason.PROVIDER_CHECK_FAILED
