"""Storage-neutral workflow audit records."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from trussium.workflows.contracts import WorkflowStatus


class WorkflowAuditEvent(StrEnum):
    """Stable lifecycle event names for workflow audit consumers."""

    STARTED = "workflow.execution.started"
    COMPLETED = "workflow.execution.completed"
    TIMED_OUT = "workflow.execution.timeout"
    CANCELLED = "workflow.execution.cancelled"
    ADMISSION_REJECTED = "workflow.admission.rejected"


class WorkflowAuditRecord(BaseModel):
    """Immutable, payload-free audit envelope with bounded workflow metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event: WorkflowAuditEvent
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    request_id: str | None = Field(default=None, min_length=1, max_length=128)
    execution_id: str | None = Field(default=None, min_length=1, max_length=128)
    status: WorkflowStatus | None = None
    reason_code: str | None = Field(default=None, min_length=1, max_length=128)
    step_count: int = Field(default=0, ge=0, le=16)
    parallel_group_count: int = Field(default=0, ge=0, le=16)

    @property
    def contains_payload(self) -> bool:
        """Audit records intentionally never carry tool or model payloads."""
        return False


class WorkflowAuditSink(Protocol):
    """Application-owned asynchronous consumer for audit records."""

    async def emit(self, record: WorkflowAuditRecord) -> None:
        """Consume one immutable, payload-free audit record."""


class NullWorkflowAuditSink:
    """Default sink that deliberately discards audit records."""

    async def emit(self, record: WorkflowAuditRecord) -> None:
        del record
