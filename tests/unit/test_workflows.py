"""Tests for bounded workflow execution."""

import pytest
from pydantic import BaseModel, ConfigDict

from trussium.tools import RegisteredTool, ToolExecutor, ToolInvocation, ToolRegistry
from trussium.workflows import WorkflowExecutor, WorkflowRequest, WorkflowStep


class EchoArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value: str


async def _echo(arguments: BaseModel) -> dict[str, object]:
    return {"value": arguments.model_dump()["value"]}


@pytest.mark.anyio
async def test_workflow_executes_declared_steps_in_order() -> None:
    executor = WorkflowExecutor(
        ToolExecutor(ToolRegistry((RegisteredTool("echo", EchoArguments, _echo),)))
    )
    result = await executor.execute(
        WorkflowRequest(
            steps=(
                WorkflowStep(
                    id="one", invocation=ToolInvocation(name="echo", arguments={"value": "a"})
                ),
                WorkflowStep(
                    id="two", invocation=ToolInvocation(name="echo", arguments={"value": "b"})
                ),
            )
        )
    )
    assert result.status == "completed"
    assert [step.output for step in result.steps] == [{"value": "a"}, {"value": "b"}]


@pytest.mark.anyio
async def test_workflow_deadline_returns_bounded_timeout() -> None:
    async def slow(_: BaseModel) -> dict[str, object]:
        import asyncio

        await asyncio.sleep(0.05)
        return {}

    executor = WorkflowExecutor(
        ToolExecutor(ToolRegistry((RegisteredTool("slow", EchoArguments, slow),)))
    )
    result = await executor.execute(
        WorkflowRequest(
            steps=(
                WorkflowStep(
                    id="slow", invocation=ToolInvocation(name="slow", arguments={"value": "x"})
                ),
            ),
            deadline_seconds=0.001,
        )
    )
    assert result.status == "timed_out"
    assert result.steps == ()
