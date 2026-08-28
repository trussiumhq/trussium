"""Bounded provider circuit-breaker state."""

from time import monotonic


class CircuitBreaker:
    """Open a provider circuit after repeated failures, then allow recovery."""

    def __init__(self, *, failure_threshold: int = 5, reset_seconds: float = 30.0) -> None:
        if failure_threshold < 1 or reset_seconds <= 0:
            raise ValueError("Circuit-breaker threshold and reset must be positive")
        self._threshold = failure_threshold
        self._reset_seconds = reset_seconds
        self._failures: dict[str, int] = {}
        self._opened_at: dict[str, float] = {}

    def allow(self, key: str) -> bool:
        """Return whether an attempt is currently allowed for a provider key."""
        opened_at = self._opened_at.get(key)
        if opened_at is None:
            return True
        if monotonic() - opened_at >= self._reset_seconds:
            self._opened_at.pop(key, None)
            self._failures[key] = 0
            return True
        return False

    def record_success(self, key: str) -> None:
        """Close and reset a provider circuit after a successful attempt."""
        self._failures.pop(key, None)
        self._opened_at.pop(key, None)

    def record_failure(self, key: str) -> None:
        """Record one failure and open the circuit at the configured threshold."""
        failures = self._failures.get(key, 0) + 1
        self._failures[key] = failures
        if failures >= self._threshold:
            self._opened_at.setdefault(key, monotonic())


__all__ = ["CircuitBreaker"]
