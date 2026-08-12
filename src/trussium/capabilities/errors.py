"""Provider-neutral capability execution errors."""

from enum import StrEnum

from trussium.errors import CapabilityError


class CapabilityErrorCategory(StrEnum):
    """Classify capability failures independently of transport protocols."""

    INVALID_REQUEST = "invalid_request"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXCEEDED = "quota_exceeded"
    UPSTREAM_AUTHENTICATION = "upstream_authentication"
    UPSTREAM_PERMISSION = "upstream_permission"
    UPSTREAM_TIMEOUT = "upstream_timeout"
    UPSTREAM_CONNECTION = "upstream_connection"
    UPSTREAM_FAILURE = "upstream_failure"


class CapabilityExecutionError(CapabilityError):
    """Represent a normalized capability execution failure.

    Attributes:
        code: Stable machine-readable error code.
        message: Client-safe error description.
        category: Protocol-neutral error classification.
    """

    def __init__(
        self,
        *,
        code: str,
        message: str,
        category: CapabilityErrorCategory,
    ) -> None:
        """Initialize a normalized capability execution error.

        Args:
            code: Stable machine-readable error code.
            message: Client-safe error description.
            category: Protocol-neutral error classification.
        """
        super().__init__(message, code=code)
        self.category = category
