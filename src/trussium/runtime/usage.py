"""Bounded process-local usage metering and token accounting."""

from dataclasses import dataclass

from trussium.runtime.context import get_execution_context


@dataclass(frozen=True, slots=True)
class UsageSnapshot:
    """Aggregated usage for one identity bucket."""

    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class UsageQuotaExceededError(Exception):
    """Raised when an identity would exceed its configured usage quota."""


class UsageMeter:
    """Keep bounded process-local request and token aggregates."""

    def __init__(
        self,
        *,
        max_identities: int = 10_000,
        max_requests: int = 0,
        max_tokens: int = 0,
    ) -> None:
        self._max_identities = max_identities
        self._max_requests = max_requests
        self._max_tokens = max_tokens
        self._usage: dict[str, UsageSnapshot] = {}

    def request_allowed(self) -> bool:
        """Return whether one more request fits the configured request quota."""
        if self._max_requests <= 0:
            return True
        current = self._usage.get(self._identity_key(), UsageSnapshot())
        return current.requests < self._max_requests

    def record(
        self,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
    ) -> None:
        """Record one request using the active identity scope."""
        key = self._identity_key()
        if key not in self._usage and len(self._usage) >= self._max_identities:
            return
        previous = self._usage.get(key, UsageSnapshot())
        if self._max_tokens > 0 and previous.total_tokens + total_tokens > self._max_tokens:
            raise UsageQuotaExceededError("Token usage quota exceeded")
        self._usage[key] = UsageSnapshot(
            requests=previous.requests + 1,
            input_tokens=previous.input_tokens + input_tokens,
            output_tokens=previous.output_tokens + output_tokens,
            total_tokens=previous.total_tokens + total_tokens,
        )

    def snapshot(self) -> dict[str, UsageSnapshot]:
        """Return a copy of all bounded usage aggregates."""
        return dict(self._usage)

    @staticmethod
    def _identity_key() -> str:
        context = get_execution_context()
        return ":".join(
            value or "-"
            for value in (context.tenant_id, context.project_id, context.application_id)
        )
