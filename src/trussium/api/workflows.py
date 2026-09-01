"""Bounded workflow execution endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError

from trussium.tools import ToolNotFoundError
from trussium.workflows import WorkflowExecutor, WorkflowRequest, WorkflowResult

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
    workflow: WorkflowRequest,
    executor: Annotated[WorkflowExecutor, Depends(get_workflow_executor)],
) -> WorkflowResult:
    try:
        return await executor.execute(workflow)
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
