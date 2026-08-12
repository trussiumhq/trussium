"""Stable exception hierarchy for Trussium-owned failures."""

from typing import ClassVar


class TrussiumError(RuntimeError):
    """Base for failures intentionally defined and safe to classify by Trussium.

    Attributes:
        code: Stable machine-readable error code.
        message: Client-safe error description.
    """

    default_code: ClassVar[str] = "trussium_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        """Initialize a Trussium-owned error with bounded public attributes."""
        resolved_code = self.default_code if code is None else code

        if not resolved_code.strip():
            raise ValueError("Error code must not be empty")

        if not message.strip():
            raise ValueError("Error message must not be empty")

        super().__init__(message)
        self.code = resolved_code
        self.message = message


class ConfigurationError(TrussiumError):
    """Base for normalized Trussium configuration failures."""

    default_code = "configuration_error"


class RuntimeExecutionError(TrussiumError):
    """Base for failures produced while operating the runtime."""

    default_code = "runtime_execution_error"


class LifecycleError(RuntimeExecutionError):
    """Base for normalized startup, drain, and shutdown failures."""

    default_code = "lifecycle_error"


class DependencyError(RuntimeExecutionError):
    """Base for normalized runtime dependency failures."""

    default_code = "dependency_error"


class CapabilityError(RuntimeExecutionError):
    """Base for provider-neutral capability failures."""

    default_code = "capability_error"


class ProviderError(CapabilityError):
    """Base for normalized provider-adapter failures."""

    default_code = "provider_error"


__all__ = [
    "CapabilityError",
    "ConfigurationError",
    "DependencyError",
    "LifecycleError",
    "ProviderError",
    "RuntimeExecutionError",
    "TrussiumError",
]
