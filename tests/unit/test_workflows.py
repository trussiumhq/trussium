"""Tests for bounded workflow execution."""

import asyncio

import pytest
from pydantic import BaseModel, ConfigDict

from trussium.tools import RegisteredTool, ToolExecutor, ToolInvocation, ToolRegistry
from trussium.workflows import WorkflowExecutor, WorkflowRequest, WorkflowStep


@pytest.fixture
def anyio_backend() -> str:
    """Run asyncio-specific workflow tests on the asyncio backend."""
    return "asyncio"


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
    cleaned = False

    async def slow(_: BaseModel) -> dict[str, object]:
        nonlocal cleaned
        import asyncio

        try:
            await asyncio.sleep(0.05)
            return {}
        finally:
            cleaned = True

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
    assert cleaned


@pytest.mark.anyio
async def test_workflow_cancellation_cleans_up_active_parallel_children() -> None:
    started = 0
    all_started = asyncio.Event()
    cleaned = 0

    async def cancellable(_: BaseModel) -> dict[str, object]:
        nonlocal started, cleaned
        started += 1
        if started == 2:
            all_started.set()
        try:
            await asyncio.sleep(10)
        finally:
            cleaned += 1
        return {}

    executor = WorkflowExecutor(
        ToolExecutor(
            ToolRegistry(
                (
                    RegisteredTool("echo", EchoArguments, _echo),
                    RegisteredTool("wait", EchoArguments, cancellable),
                )
            )
        )
    )
    workflow = asyncio.create_task(
        executor.execute(
            WorkflowRequest(
                steps=(
                    WorkflowStep(
                        id="root",
                        invocation=ToolInvocation(name="echo", arguments={"value": "root"}),
                    ),
                ),
                parallel_groups=(
                    (
                        WorkflowStep(
                            id="one",
                            invocation=ToolInvocation(name="wait", arguments={"value": "x"}),
                        ),
                        WorkflowStep(
                            id="two",
                            invocation=ToolInvocation(name="wait", arguments={"value": "x"}),
                        ),
                    ),
                ),
            )
        )
    )
    await all_started.wait()
    workflow.cancel()
    with pytest.raises(asyncio.CancelledError):
        await workflow
    assert cleaned == 2


@pytest.mark.anyio
async def test_workflow_parallel_group_preserves_declaration_order() -> None:
    executor = WorkflowExecutor(
        ToolExecutor(ToolRegistry((RegisteredTool("echo", EchoArguments, _echo),)))
    )
    result = await executor.execute(
        WorkflowRequest(
            steps=(
                WorkflowStep(
                    id="start", invocation=ToolInvocation(name="echo", arguments={"value": "s"})
                ),
            ),
            parallel_groups=(
                (
                    WorkflowStep(
                        id="first", invocation=ToolInvocation(name="echo", arguments={"value": "a"})
                    ),
                    WorkflowStep(
                        id="second",
                        invocation=ToolInvocation(name="echo", arguments={"value": "b"}),
                    ),
                ),
            ),
        )
    )
    assert [step.output for step in result.steps] == [
        {"value": "s"},
        {"value": "a"},
        {"value": "b"},
    ]


def test_workflow_rejects_duplicate_step_ids_before_execution() -> None:
    with pytest.raises(ValueError, match="step IDs must be unique"):
        WorkflowRequest(
            steps=(WorkflowStep(id="same", invocation=ToolInvocation(name="echo", arguments={})),),
            parallel_groups=(
                (WorkflowStep(id="same", invocation=ToolInvocation(name="echo", arguments={})),),
            ),
        )


def test_workflow_rejects_parallel_groups_over_eight_steps() -> None:
    with pytest.raises(ValueError, match="one to eight steps"):
        WorkflowRequest(
            steps=(WorkflowStep(id="root", invocation=ToolInvocation(name="echo", arguments={})),),
            parallel_groups=(
                tuple(
                    WorkflowStep(
                        id=f"step-{index}",
                        invocation=ToolInvocation(name="echo", arguments={}),
                    )
                    for index in range(9)
                ),
            ),
        )
