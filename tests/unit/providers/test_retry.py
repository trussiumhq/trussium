from trussium.capabilities.errors import CapabilityErrorCategory, CapabilityExecutionError
from trussium.providers import ProviderFailureClass, RetryPolicy, classify_failure


def test_retry_policy_uses_bounded_exponential_backoff() -> None:
    policy = RetryPolicy(max_attempts=3, base_delay_seconds=0.5, max_delay_seconds=0.75)
    error = CapabilityExecutionError(
        code="upstream_timeout",
        message="timeout",
        category=CapabilityErrorCategory.UPSTREAM_TIMEOUT,
    )

    assert policy.decide(1, error).retry is True
    assert policy.decide(1, error).delay_seconds == 0.5
    assert policy.decide(2, error).delay_seconds == 0.75
    assert policy.decide(3, error).retry is False


def test_non_retryable_failures_are_classified_without_retry() -> None:
    policy = RetryPolicy()
    error = CapabilityExecutionError(
        code="invalid_request",
        message="invalid",
        category=CapabilityErrorCategory.INVALID_REQUEST,
    )

    decision = policy.decide(1, error)
    assert decision.failure_class is ProviderFailureClass.INVALID_REQUEST
    assert decision.retry is False
    assert classify_failure(TimeoutError()) is ProviderFailureClass.TIMEOUT


def test_retry_policy_rejects_invalid_attempt_budget() -> None:
    try:
        RetryPolicy(max_attempts=0)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid retry budget should fail")
