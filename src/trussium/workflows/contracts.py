"""Immutable contracts for bounded workflows."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    parallel_groups: tuple[tuple[WorkflowStep, ...], ...] = ()
    deadline_seconds: float = Field(default=30.0, gt=0, le=300)
    depth: int = Field(default=1, ge=1, le=4)

    @model_validator(mode="after")
    def validate_admission_limits(self) -> "WorkflowRequest":
        if any(not group or len(group) > 8 for group in self.parallel_groups):
            raise ValueError("Parallel workflow groups must contain one to eight steps")
        all_steps = self.steps + tuple(step for group in self.parallel_groups for step in group)
        if len(all_steps) > 16:
            raise ValueError("Workflows cannot contain more than sixteen child steps")
        step_ids = [step.id for step in all_steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("Workflow step IDs must be unique")
        return self


class WorkflowResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: WorkflowStatus
    steps: tuple[ToolExecutionResult, ...] = ()
