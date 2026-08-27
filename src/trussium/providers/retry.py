"""Bounded provider retry decisions and failure classification."""

import asyncio
from dataclasses import dataclass
from enum import StrEnum

from trussium.capabilities.errors import CapabilityErrorCategory, CapabilityExecutionError


class ProviderFailureClass(StrEnum):
    """Stable classes used to decide whether a provider attempt may retry."""

    CANCELLATION = "cancellation"
    INVALID_REQUEST = "invalid_request"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXCEEDED = "quota_exceeded"
    AUTHENTICATION = "authentication"
    PERMISSION = "permission"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    UPSTREAM = "upstream"
    UNEXPECTED = "unexpected"


def classify_failure(error: BaseException) -> ProviderFailureClass:
    """Classify a failure without exposing transport-specific details."""
    if isinstance(error, asyncio.CancelledError | KeyboardInterrupt | SystemExit):
        return ProviderFailureClass.CANCELLATION
    if isinstance(error, TimeoutError):  # includes asyncio.TimeoutError
        return ProviderFailureClass.TIMEOUT
    if isinstance(error, ConnectionError):
        return ProviderFailureClass.CONNECTION
    if isinstance(error, CapabilityExecutionError):
        return {
            CapabilityErrorCategory.INVALID_REQUEST: ProviderFailureClass.INVALID_REQUEST,
            CapabilityErrorCategory.RATE_LIMITED: ProviderFailureClass.RATE_LIMITED,
            CapabilityErrorCategory.QUOTA_EXCEEDED: ProviderFailureClass.QUOTA_EXCEEDED,
            CapabilityErrorCategory.UPSTREAM_AUTHENTICATION: ProviderFailureClass.AUTHENTICATION,
            CapabilityErrorCategory.UPSTREAM_PERMISSION: ProviderFailureClass.PERMISSION,
            CapabilityErrorCategory.UPSTREAM_TIMEOUT: ProviderFailureClass.TIMEOUT,
            CapabilityErrorCategory.UPSTREAM_CONNECTION: ProviderFailureClass.CONNECTION,
            CapabilityErrorCategory.UPSTREAM_FAILURE: ProviderFailureClass.UPSTREAM,
        }[error.category]
    return ProviderFailureClass.UNEXPECTED


@dataclass(frozen=True, slots=True)
class RetryDecision:
    """Immutable result for one provider attempt."""

    attempt: int
    retry: bool
    delay_seconds: float
    failure_class: ProviderFailureClass


class RetryPolicy:
    """Apply bounded exponential backoff to explicitly retryable failures."""

    def __init__(
        self,
        *,
        max_attempts: int = 3,
        base_delay_seconds: float = 0.25,
        max_delay_seconds: float = 10.0,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("Retry max attempts must be at least 1")
        if base_delay_seconds < 0 or max_delay_seconds < base_delay_seconds:
            raise ValueError("Retry delays must be non-negative and ordered")
        self._max_attempts = max_attempts
        self._base_delay_seconds = base_delay_seconds
        self._max_delay_seconds = max_delay_seconds

    @property
    def max_attempts(self) -> int:
        return self._max_attempts

    def decide(self, attempt: int, error: BaseException) -> RetryDecision:
        """Return a deterministic decision for a one-based attempt number."""
        if attempt < 1 or attempt > self._max_attempts:
            raise ValueError("Retry attempt must be within the configured attempt budget")
        failure_class = classify_failure(error)
        retry = attempt < self._max_attempts and failure_class in {
            ProviderFailureClass.RATE_LIMITED,
            ProviderFailureClass.TIMEOUT,
            ProviderFailureClass.CONNECTION,
            ProviderFailureClass.UPSTREAM,
        }
        delay = min(self._base_delay_seconds * (2 ** (attempt - 1)), self._max_delay_seconds)
        return RetryDecision(attempt, retry, delay if retry else 0.0, failure_class)


__all__ = ["ProviderFailureClass", "RetryDecision", "RetryPolicy", "classify_failure"]
