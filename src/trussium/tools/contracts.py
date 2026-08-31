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


class ToolMetadata(BaseModel):
    """Bounded informational metadata safe for discovery responses."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    version: str = Field(default="1.0.0", min_length=1, max_length=32)
    description: str = Field(default="", max_length=256)


@dataclass(frozen=True, slots=True)
class RegisteredTool:
    name: str
    arguments_model: type[BaseModel]
    handler: ToolHandler
    version: str = "1.0.0"
    description: str = ""

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(name=self.name, version=self.version, description=self.description)
