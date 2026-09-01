"""Sequential bounded workflow execution over registered tools."""

import asyncio
from asyncio import timeout

from trussium.runtime import bind_execution_context, generate_execution_id
from trussium.tools import ToolExecutor
from trussium.workflows.contracts import WorkflowRequest, WorkflowResult, WorkflowStatus
from trussium.workflows.policy import WorkflowAdmissionPolicy


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

    async def execute(self, request: WorkflowRequest) -> WorkflowResult:
        self._admission_policy.validate(request)
        results = []
        with bind_execution_context(
            capability="agent.workflows", execution_id=generate_execution_id()
        ):
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
                return WorkflowResult(status=WorkflowStatus.TIMED_OUT, steps=tuple(results))
            except BaseException:
                raise
        return WorkflowResult(status=WorkflowStatus.COMPLETED, steps=tuple(results))
