"""Controlled declared-tool execution endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError

from trussium.tools import (
    ToolApprovalTimeoutError,
    ToolAuthorizationError,
    ToolExecutionResult,
    ToolExecutor,
    ToolInvocation,
    ToolMetadata,
    ToolNotFoundError,
)

router = APIRouter(prefix="/v1", tags=["tools"])


def get_tool_executor(request: Request) -> ToolExecutor:
    executor = getattr(request.app.state, "tool_executor", None)
    if not isinstance(executor, ToolExecutor):
        raise HTTPException(
            status_code=503,
            detail={"code": "tools_unavailable", "message": "No tools are configured."},
        )
    return executor


@router.get("/tools", response_model=tuple[ToolMetadata, ...])
async def list_tools(
    executor: Annotated[ToolExecutor, Depends(get_tool_executor)],
) -> tuple[ToolMetadata, ...]:
    """List safe metadata for explicitly registered tools."""
    return executor.registry.discover()


@router.post("/tools/executions", response_model=ToolExecutionResult)
async def execute_tool(
    invocation: ToolInvocation,
    executor: Annotated[ToolExecutor, Depends(get_tool_executor)],
) -> ToolExecutionResult:
    try:
        return await executor.execute(invocation)
    except ToolNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail={"code": "tool_not_found", "message": str(error)},
        ) from error
    except ToolAuthorizationError as error:
        raise HTTPException(
            status_code=403,
            detail={"code": error.reason_code, "message": "Tool authorization was denied."},
        ) from error
    except ValidationError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_tool_arguments", "message": "Tool arguments are invalid."},
        ) from error
    except ToolApprovalTimeoutError as error:
        raise HTTPException(
            status_code=504,
            detail={"code": "approval_timed_out", "message": "Tool approval timed out."},
        ) from error
    except TimeoutError as error:
        raise HTTPException(
            status_code=504,
            detail={"code": "tool_execution_timed_out", "message": "Tool execution timed out."},
        ) from error
