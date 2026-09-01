"""Tests for bounded workflow execution."""

import asyncio
import logging

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from trussium.tools import RegisteredTool, ToolExecutor, ToolInvocation, ToolRegistry
from trussium.workflows import (
    WorkflowAdmissionError,
    WorkflowAdmissionPolicy,
    WorkflowAuditEvent,
    WorkflowAuditRecord,
    WorkflowAuditSink,
    WorkflowExecutor,
    WorkflowRequest,
    WorkflowStatus,
    WorkflowStep,
)


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


@pytest.mark.anyio
async def test_workflow_policy_rejects_before_tool_execution() -> None:
    executed = False

    async def handler(arguments: BaseModel) -> dict[str, object]:
        nonlocal executed
        executed = True
        return {}

    executor = WorkflowExecutor(
        ToolExecutor(ToolRegistry((RegisteredTool("echo", EchoArguments, handler),))),
        admission_policy=WorkflowAdmissionPolicy(max_depth=1),
    )
    request = WorkflowRequest(
        steps=(WorkflowStep(id="one", invocation=ToolInvocation(name="echo", arguments={})),),
        depth=2,
    )

    with pytest.raises(WorkflowAdmissionError, match="depth") as error:
        await executor.execute(request)
    assert error.value.code == "workflow_depth_exceeded"
    assert executed is False


@pytest.mark.anyio
async def test_workflow_logs_lifecycle_without_tool_payloads(
    caplog: pytest.LogCaptureFixture,
) -> None:
    executor = WorkflowExecutor(
        ToolExecutor(ToolRegistry((RegisteredTool("echo", EchoArguments, _echo),)))
    )
    with caplog.at_level(logging.INFO, logger="trussium.workflows.execution"):
        await executor.execute(
            WorkflowRequest(
                steps=(
                    WorkflowStep(
                        id="one",
                        invocation=ToolInvocation(
                            name="echo", arguments={"value": "sensitive-input"}
                        ),
                    ),
                )
            )
        )

    events = [
        getattr(record, "event", None)
        for record in caplog.records
        if record.name == "trussium.workflows.execution"
    ]
    assert events == ["workflow.execution.started", "workflow.execution.completed"]
    assert all("sensitive-input" not in record.getMessage() for record in caplog.records)


@pytest.mark.anyio
async def test_workflow_audit_sink_receives_ordered_records() -> None:
    records = []

    class Sink:
        async def emit(self, record: WorkflowAuditRecord) -> None:
            records.append(record)

    sink: WorkflowAuditSink = Sink()
    executor = WorkflowExecutor(
        ToolExecutor(ToolRegistry((RegisteredTool("echo", EchoArguments, _echo),))),
        audit_sink=sink,
    )
    await executor.execute(
        WorkflowRequest(
            steps=(
                WorkflowStep(
                    id="one", invocation=ToolInvocation(name="echo", arguments={"value": "ok"})
                ),
            )
        )
    )

    assert [record.event for record in records] == [
        WorkflowAuditEvent.STARTED,
        WorkflowAuditEvent.COMPLETED,
    ]
    assert all(record.contains_payload is False for record in records)


@pytest.mark.anyio
async def test_workflow_audit_sink_failure_does_not_fail_execution() -> None:
    class FailingSink:
        async def emit(self, record: WorkflowAuditRecord) -> None:
            raise RuntimeError("sink unavailable")

    executor = WorkflowExecutor(
        ToolExecutor(ToolRegistry((RegisteredTool("echo", EchoArguments, _echo),))),
        audit_sink=FailingSink(),
    )
    result = await executor.execute(
        WorkflowRequest(
            steps=(
                WorkflowStep(
                    id="one", invocation=ToolInvocation(name="echo", arguments={"value": "ok"})
                ),
            )
        )
    )
    assert result.status == WorkflowStatus.COMPLETED


@pytest.mark.anyio
async def test_slow_workflow_audit_sink_is_bounded() -> None:
    class SlowSink:
        async def emit(self, record: WorkflowAuditRecord) -> None:
            await asyncio.sleep(1)

    executor = WorkflowExecutor(
        ToolExecutor(ToolRegistry((RegisteredTool("echo", EchoArguments, _echo),))),
        audit_sink=SlowSink(),
        audit_delivery_timeout_seconds=0.001,
    )
    result = await executor.execute(
        WorkflowRequest(
            steps=(
                WorkflowStep(
                    id="one", invocation=ToolInvocation(name="echo", arguments={"value": "ok"})
                ),
            )
        )
    )
    assert result.status == WorkflowStatus.COMPLETED


def test_audit_delivery_timeout_must_be_positive() -> None:
    with pytest.raises(ValueError, match="Audit delivery timeout"):
        WorkflowExecutor(
            ToolExecutor(ToolRegistry()),
            audit_delivery_timeout_seconds=0,
        )


def test_workflow_audit_record_is_immutable_and_payload_free() -> None:
    record = WorkflowAuditRecord(
        event=WorkflowAuditEvent.COMPLETED,
        request_id="request-1",
        execution_id="execution-1",
        status=WorkflowStatus.COMPLETED,
        step_count=2,
        parallel_group_count=1,
    )

    assert record.contains_payload is False
    assert record.model_dump(mode="json")["event"] == "workflow.execution.completed"
    with pytest.raises(ValidationError):
        record.step_count = 3
