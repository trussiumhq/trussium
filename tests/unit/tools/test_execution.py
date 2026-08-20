import asyncio

import pytest
from pydantic import BaseModel, ConfigDict

from trussium.tools import (
    RegisteredTool,
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
