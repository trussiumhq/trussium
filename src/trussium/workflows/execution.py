"""Sequential bounded workflow execution over registered tools."""

import asyncio
from asyncio import timeout

from trussium.observability import (
    WORKFLOW_ADMISSION_REJECTED,
    WORKFLOW_EXECUTION_CANCELLED,
    WORKFLOW_EXECUTION_COMPLETED,
    WORKFLOW_EXECUTION_STARTED,
    WORKFLOW_EXECUTION_TIMEOUT,
    get_logger,
)
from trussium.runtime import bind_execution_context, generate_execution_id
from trussium.tools import ToolExecutor
from trussium.workflows.contracts import WorkflowRequest, WorkflowResult, WorkflowStatus
from trussium.workflows.policy import WorkflowAdmissionError, WorkflowAdmissionPolicy


class WorkflowExecutor:
    """Execute one bounded workflow of declared tool steps."""

    def __init__(
        self,
        tool_executor: ToolExecutor,
        *,
        admission_policy: WorkflowAdmissionPolicy | None = None,
    ) -> None:
        self._tool_executor = tool_executor
        self._admission_policy = admission_policy or WorkflowAdmissionPolicy()
        self._logger = get_logger("workflows.execution")

    async def execute(self, request: WorkflowRequest) -> WorkflowResult:
        try:
            self._admission_policy.validate(request)
        except WorkflowAdmissionError as error:
            self._logger.warning(
                "Workflow admission rejected",
                extra={
                    "event": WORKFLOW_ADMISSION_REJECTED,
                    "workflow_admission_code": error.code,
                    "workflow_step_count": len(request.steps),
                    "workflow_parallel_group_count": len(request.parallel_groups),
                },
            )
            raise
        results = []
        execution_id = generate_execution_id()
        with bind_execution_context(capability="agent.workflows", execution_id=execution_id):
            self._logger.info(
                "Workflow execution started",
                extra={
                    "event": WORKFLOW_EXECUTION_STARTED,
                    "workflow_step_count": len(request.steps),
                    "workflow_parallel_group_count": len(request.parallel_groups),
                },
            )
            try:
                async with timeout(request.deadline_seconds):
                    for step in request.steps:
                        results.append(await self._tool_executor.execute(step.invocation))
                    for group in request.parallel_groups:
                        if len(group) > 8:
                            raise ValueError(
                                "Parallel workflow groups cannot exceed eight children"
                            )
                        tasks = [
                            asyncio.create_task(self._tool_executor.execute(step.invocation))
                            for step in group
                        ]
                        try:
                            results.extend(await asyncio.gather(*tasks))
                        finally:
                            for task in tasks:
                                if not task.done():
                                    task.cancel()
            except TimeoutError:
                self._logger.warning(
                    "Workflow execution timed out",
                    extra={"event": WORKFLOW_EXECUTION_TIMEOUT, "workflow_status": "timed_out"},
                )
                return WorkflowResult(status=WorkflowStatus.TIMED_OUT, steps=tuple(results))
            except asyncio.CancelledError:
                self._logger.warning(
                    "Workflow execution cancelled",
                    extra={"event": WORKFLOW_EXECUTION_CANCELLED, "workflow_status": "cancelled"},
                )
                raise
        self._logger.info(
            "Workflow execution completed",
            extra={"event": WORKFLOW_EXECUTION_COMPLETED, "workflow_status": "completed"},
        )
        return WorkflowResult(status=WorkflowStatus.COMPLETED, steps=tuple(results))
