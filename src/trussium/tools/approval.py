"""Optional, deployment-owned human-approval contracts for tools."""

from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class ToolApprovalDecision(StrEnum):
    """Bounded outcomes returned by an approval adapter."""

    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class ToolApprovalRequest(BaseModel):
    """Privacy-safe approval request created after policy requests approval."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str = Field(min_length=1, max_length=128)
    parent_execution_id: str = Field(min_length=1, max_length=128)
    tool_name: str = Field(min_length=1, max_length=128)
    tool_version: str = Field(min_length=1, max_length=32)
    identity: str = Field(min_length=1, max_length=128)
    created_at: datetime
    expires_at: datetime
    reason_code: str = Field(min_length=1, max_length=64)


class ToolApprovalResult(BaseModel):
    """Stable approval result with no UI, payload, or exception details."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: ToolApprovalDecision
    reason_code: str = Field(min_length=1, max_length=64)


class ToolApprovalTimeoutError(TimeoutError):
    """Raised when an approval adapter does not decide within its bound."""

    def __init__(self) -> None:
        super().__init__("Tool approval timed out.")


@runtime_checkable
class ToolApprovalAdapter(Protocol):
    """Application-owned asynchronous approval integration point."""

    async def request_approval(self, request: ToolApprovalRequest) -> ToolApprovalResult:
        """Return one bounded approval result before handler execution."""


__all__ = [
    "ToolApprovalAdapter",
    "ToolApprovalDecision",
    "ToolApprovalRequest",
    "ToolApprovalResult",
    "ToolApprovalTimeoutError",
]
