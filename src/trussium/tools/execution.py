"""Bounded execution of declared in-process tools."""

from asyncio import timeout
from math import isfinite

from trussium.observability import (
    TOOL_EXECUTION_COMPLETED,
    TOOL_EXECUTION_FAILED,
    TOOL_EXECUTION_STARTED,
    TOOL_EXECUTION_TIMEOUT,
    get_logger,
)
from trussium.runtime import bind_execution_context
from trussium.tools.contracts import ToolExecutionResult, ToolInvocation
from trussium.tools.registry import ToolRegistry


class ToolExecutor:
    def __init__(self, registry: ToolRegistry, *, timeout_seconds: float = 10.0) -> None:
        if not isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("Tool execution timeout must be finite and positive")
        self._registry = registry
        self._timeout_seconds = timeout_seconds
        self._logger = get_logger("tools.execution")

    @property
    def registry(self) -> ToolRegistry:
        """Return the application-owned tool registry."""
        return self._registry

    async def execute(self, invocation: ToolInvocation) -> ToolExecutionResult:
        tool = self._registry.require(invocation.name)
        with bind_execution_context(capability="tools.executions"):
            self._logger.info(
                "Tool execution started",
                extra={"event": TOOL_EXECUTION_STARTED, "tool_name": tool.name},
            )
            try:
                arguments = tool.arguments_model.model_validate(invocation.arguments)
                async with timeout(self._timeout_seconds):
                    output = await tool.handler(arguments)
            except TimeoutError:
                self._logger.warning(
                    "Tool execution timed out",
                    extra={"event": TOOL_EXECUTION_TIMEOUT, "tool_name": tool.name},
                )
                raise
            except Exception:
                self._logger.warning(
                    "Tool execution failed",
                    extra={"event": TOOL_EXECUTION_FAILED, "tool_name": tool.name},
                )
                raise

            self._logger.info(
                "Tool execution completed",
                extra={"event": TOOL_EXECUTION_COMPLETED, "tool_name": tool.name},
            )
            return ToolExecutionResult(tool_name=tool.name, output=output)
