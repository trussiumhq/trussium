"""Sequential bounded workflow execution over registered tools."""

from asyncio import timeout

from trussium.runtime import bind_execution_context, generate_execution_id
from trussium.tools import ToolExecutor
from trussium.workflows.contracts import WorkflowRequest, WorkflowResult, WorkflowStatus


class WorkflowExecutor:
    """Execute one bounded workflow of declared tool steps."""

    def __init__(self, tool_executor: ToolExecutor) -> None:
        self._tool_executor = tool_executor

    async def execute(self, request: WorkflowRequest) -> WorkflowResult:
        results = []
        with bind_execution_context(
            capability="agent.workflows", execution_id=generate_execution_id()
        ):
            try:
                async with timeout(request.deadline_seconds):
                    for step in request.steps:
                        results.append(await self._tool_executor.execute(step.invocation))
            except TimeoutError:
                return WorkflowResult(status=WorkflowStatus.TIMED_OUT, steps=tuple(results))
            except BaseException:
                raise
        return WorkflowResult(status=WorkflowStatus.COMPLETED, steps=tuple(results))
