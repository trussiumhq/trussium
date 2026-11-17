"""Bounded workflow execution endpoint."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError

from trussium.tools import ToolNotFoundError
from trussium.workflows import (
    WorkflowAdmissionError,
    WorkflowExecutor,
    WorkflowRequest,
    WorkflowResult,
)

router = APIRouter(prefix="/v1", tags=["workflows"])


def get_workflow_executor(request: Request) -> WorkflowExecutor:
    executor = getattr(request.app.state, "workflow_executor", None)
    if not isinstance(executor, WorkflowExecutor):
        raise HTTPException(
            status_code=503,
            detail={"code": "workflows_unavailable", "message": "No tools are configured."},
        )
    return executor


@router.post("/workflows/executions", response_model=WorkflowResult)
async def execute_workflow(
    request: Request,
    workflow: WorkflowRequest,
    executor: Annotated[WorkflowExecutor, Depends(get_workflow_executor)],
) -> WorkflowResult:
    execution = asyncio.create_task(executor.execute(workflow))
    disconnect = asyncio.create_task(_wait_for_disconnect(request))
    try:
        done, _ = await asyncio.wait((execution, disconnect), return_when=asyncio.FIRST_COMPLETED)
        if disconnect in done:
            execution.cancel()
        return await execution
    except WorkflowAdmissionError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": error.code, "message": str(error)},
        ) from error
    except ToolNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail={"code": "tool_not_found", "message": str(error)},
        ) from error
    except ValidationError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_tool_arguments", "message": "Tool arguments are invalid."},
        ) from error
    except TimeoutError as error:
        raise HTTPException(
            status_code=504,
            detail={"code": "tool_execution_timed_out", "message": "Tool execution timed out."},
        ) from error
    finally:
        for task in (execution, disconnect):
            if not task.done():
                task.cancel()
        await asyncio.gather(execution, disconnect, return_exceptions=True)


async def _wait_for_disconnect(request: Request) -> None:
    """Wait for the ASGI server to report that the caller closed its connection."""
    while True:
        message = await request.receive()
        if message["type"] == "http.disconnect":
            return
