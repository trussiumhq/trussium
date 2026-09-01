"""Optional, deployment-owned authorization contracts for tools."""

from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class ToolAuthorizationDecision(StrEnum):
    """Bounded outcomes returned by a tool policy adapter."""

    ALLOW = "allow"
    DENY = "deny"
    APPROVAL_REQUIRED = "approval_required"


class ToolAuthorizationRequest(BaseModel):
    """Privacy-safe inputs supplied to an authorization adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str | None = Field(default=None, min_length=1, max_length=128)
    execution_id: str | None = Field(default=None, min_length=1, max_length=128)
    identity: str = Field(min_length=1, max_length=128)
    tenant_id: str | None = Field(default=None, min_length=1, max_length=128)
    tool_name: str = Field(min_length=1, max_length=128)
    tool_version: str = Field(min_length=1, max_length=32)
    capability: str | None = Field(default=None, min_length=1, max_length=128)
    provider: str | None = Field(default=None, min_length=1, max_length=128)
    model: str | None = Field(default=None, min_length=1, max_length=128)
    deadline_seconds: float = Field(gt=0, le=300)
    resource_budget: int = Field(default=1, ge=1, le=16)


class ToolAuthorizationResult(BaseModel):
    """Stable policy result with no payload or exception details."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: ToolAuthorizationDecision
    reason_code: str = Field(min_length=1, max_length=64)


class ToolAuthorizationError(Exception):
    """Raised when policy prevents a tool handler from starting."""

    def __init__(self, reason_code: str = "tool_not_authorized") -> None:
        self.reason_code = reason_code
        super().__init__("Tool authorization was denied.")


@runtime_checkable
class ToolPolicyAdapter(Protocol):
    """Application-owned asynchronous policy integration point."""

    async def authorize(self, request: ToolAuthorizationRequest) -> ToolAuthorizationResult:
        """Return one bounded authorization result before handler execution."""


__all__ = [
    "ToolAuthorizationDecision",
    "ToolAuthorizationError",
    "ToolAuthorizationRequest",
    "ToolAuthorizationResult",
    "ToolPolicyAdapter",
]
