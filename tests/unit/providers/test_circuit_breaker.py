from trussium.providers import CircuitBreaker


def test_circuit_breaker_opens_after_threshold_and_resets() -> None:
    breaker = CircuitBreaker(failure_threshold=2, reset_seconds=0.01)
    breaker.record_failure("openai")
    assert breaker.allow("openai") is True
    breaker.record_failure("openai")
    assert breaker.allow("openai") is False

    import time

    time.sleep(0.02)
    assert breaker.allow("openai") is True
    breaker.record_success("openai")
    assert breaker.allow("openai") is True
