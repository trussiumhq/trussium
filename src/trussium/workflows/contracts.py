"""Immutable contracts for bounded workflows."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from trussium.tools import ToolExecutionResult, ToolInvocation


class WorkflowStatus(StrEnum):
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class WorkflowStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, max_length=64)
    invocation: ToolInvocation


class WorkflowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    steps: tuple[WorkflowStep, ...] = Field(min_length=1, max_length=16)
    deadline_seconds: float = Field(default=30.0, gt=0, le=300)
    depth: int = Field(default=1, ge=1, le=4)


class WorkflowResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: WorkflowStatus
    steps: tuple[ToolExecutionResult, ...] = ()
