"""Local admission policy for bounded workflows."""

from dataclasses import dataclass

from trussium.workflows.contracts import WorkflowRequest


class WorkflowAdmissionError(ValueError):
    """A workflow exceeded an explicit local resource limit."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class WorkflowAdmissionPolicy:
    """Immutable, process-local limits applied before child execution."""

    max_depth: int = 4
    max_steps: int = 16
    max_parallel_steps: int = 8
    max_deadline_seconds: float = 300.0

    def __post_init__(self) -> None:
        if self.max_depth < 1 or self.max_steps < 1 or self.max_parallel_steps < 1:
            raise ValueError("Workflow policy limits must be positive")
        if self.max_deadline_seconds <= 0:
            raise ValueError("Workflow policy deadline must be positive")

    def validate(self, request: WorkflowRequest) -> None:
        all_steps = request.steps + tuple(
            step for group in request.parallel_groups for step in group
        )
        if request.depth > self.max_depth:
            raise WorkflowAdmissionError(
                "workflow_depth_exceeded", "Workflow depth exceeds policy."
            )
        if len(all_steps) > self.max_steps:
            raise WorkflowAdmissionError(
                "workflow_step_limit_exceeded", "Workflow step limit exceeded."
            )
        if any(len(group) > self.max_parallel_steps for group in request.parallel_groups):
            raise WorkflowAdmissionError(
                "workflow_fanout_exceeded", "Workflow parallel fan-out exceeds policy."
            )
        if request.deadline_seconds > self.max_deadline_seconds:
            raise WorkflowAdmissionError(
                "workflow_deadline_exceeded", "Workflow deadline exceeds policy."
            )
