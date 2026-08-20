"""Safe immutable contracts for explicitly registered tools."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolInvocation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_name: str = Field(min_length=1)
    output: dict[str, Any]


ToolHandler = Callable[[BaseModel], Awaitable[dict[str, Any]]]


@dataclass(frozen=True, slots=True)
class RegisteredTool:
    name: str
    arguments_model: type[BaseModel]
    handler: ToolHandler
