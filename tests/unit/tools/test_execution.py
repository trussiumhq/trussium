import asyncio

import pytest
from pydantic import BaseModel, ConfigDict

from trussium.tools import (
    RegisteredTool,
    ToolApprovalDecision,
    ToolApprovalResult,
    ToolAuthorizationDecision,
    ToolAuthorizationError,
    ToolAuthorizationResult,
    ToolExecutor,
    ToolInvocation,
    ToolNotFoundError,
    ToolRegistry,
)


class EchoArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value: str


class EmptyArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


async def _echo(arguments: BaseModel) -> dict[str, object]:
    return {"value": arguments.model_dump()["value"]}


async def _wait(_: BaseModel) -> dict[str, object]:
    await asyncio.sleep(1)
    return {}


class DenyPolicy:
    async def authorize(self, request: object) -> ToolAuthorizationResult:
        return ToolAuthorizationResult(
            decision=ToolAuthorizationDecision.DENY, reason_code="denied_by_test"
        )


class ApprovalPolicy:
    async def authorize(self, request: object) -> ToolAuthorizationResult:
        return ToolAuthorizationResult(
            decision=ToolAuthorizationDecision.APPROVAL_REQUIRED, reason_code="needs_review"
        )


class ApproveAdapter:
    async def request_approval(self, request: object) -> ToolApprovalResult:
        return ToolApprovalResult(
            decision=ToolApprovalDecision.APPROVED, reason_code="approved_by_test"
        )


def test_declared_tool_executes() -> None:
    executor = ToolExecutor(ToolRegistry((RegisteredTool("echo", EchoArguments, _echo),)))
    result = asyncio.run(executor.execute(ToolInvocation(name="echo", arguments={"value": "ok"})))
    assert result.model_dump() == {"tool_name": "echo", "output": {"value": "ok"}}


def test_unknown_tool_is_rejected() -> None:
    executor = ToolExecutor(ToolRegistry())
    with pytest.raises(ToolNotFoundError):
        asyncio.run(executor.execute(ToolInvocation(name="shell", arguments={})))


def test_tool_timeout_is_bounded() -> None:
    executor = ToolExecutor(
        ToolRegistry((RegisteredTool("wait", EmptyArguments, _wait),)), timeout_seconds=0.01
    )
    with pytest.raises(TimeoutError):
        asyncio.run(executor.execute(ToolInvocation(name="wait", arguments={})))


def test_tool_rejects_arguments_outside_its_contract() -> None:
    executor = ToolExecutor(ToolRegistry((RegisteredTool("echo", EchoArguments, _echo),)))
    with pytest.raises(ValueError):
        asyncio.run(executor.execute(ToolInvocation(name="echo", arguments={"value": 1})))


def test_tool_execution_timeout_must_be_positive() -> None:
    with pytest.raises(ValueError, match="finite and positive"):
        ToolExecutor(ToolRegistry(), timeout_seconds=0)


def test_tool_names_must_be_unique() -> None:
    with pytest.raises(ValueError, match="more than once"):
        ToolRegistry(
            (
                RegisteredTool("echo", EchoArguments, _echo),
                RegisteredTool("echo", EchoArguments, _echo),
            )
        )


def test_policy_denial_prevents_handler_execution() -> None:
    executor = ToolExecutor(
        ToolRegistry((RegisteredTool("echo", EchoArguments, _echo),)),
        policy_adapter=DenyPolicy(),
    )
    with pytest.raises(ToolAuthorizationError, match="authorization"):
        asyncio.run(executor.execute(ToolInvocation(name="echo", arguments={"value": "no"})))


def test_approval_required_can_allow_handler_execution() -> None:
    executor = ToolExecutor(
        ToolRegistry((RegisteredTool("echo", EchoArguments, _echo),)),
        policy_adapter=ApprovalPolicy(),
        approval_adapter=ApproveAdapter(),
    )
    result = asyncio.run(executor.execute(ToolInvocation(name="echo", arguments={"value": "ok"})))
    assert result.output == {"value": "ok"}
