"""Sequential bounded workflow execution over registered tools."""

import asyncio
from asyncio import timeout
from math import isfinite

from trussium.observability import (
    WORKFLOW_ADMISSION_REJECTED,
    WORKFLOW_AUDIT_DELIVERY_TIMEOUT,
    WORKFLOW_EXECUTION_CANCELLED,
    WORKFLOW_EXECUTION_COMPLETED,
    WORKFLOW_EXECUTION_STARTED,
    WORKFLOW_EXECUTION_TIMEOUT,
    get_logger,
)
from trussium.runtime import bind_execution_context, generate_execution_id, get_execution_context
from trussium.tools import ToolExecutor
from trussium.workflows.audit import (
    NullWorkflowAuditSink,
    WorkflowAuditEvent,
    WorkflowAuditRecord,
    WorkflowAuditSink,
)
from trussium.workflows.contracts import WorkflowRequest, WorkflowResult, WorkflowStatus
from trussium.workflows.policy import WorkflowAdmissionError, WorkflowAdmissionPolicy


class WorkflowExecutor:
    """Execute one bounded workflow of declared tool steps."""

    def __init__(
        self,
        tool_executor: ToolExecutor,
        *,
        admission_policy: WorkflowAdmissionPolicy | None = None,
        audit_sink: WorkflowAuditSink | None = None,
        audit_delivery_timeout_seconds: float = 0.25,
    ) -> None:
        self._tool_executor = tool_executor
        self._admission_policy = admission_policy or WorkflowAdmissionPolicy()
        self._audit_sink = audit_sink or NullWorkflowAuditSink()
        if not isfinite(audit_delivery_timeout_seconds) or audit_delivery_timeout_seconds <= 0:
            raise ValueError("Audit delivery timeout must be finite and positive")
        self._audit_delivery_timeout_seconds = audit_delivery_timeout_seconds
        self._logger = get_logger("workflows.execution")

    async def _emit_audit(self, record: WorkflowAuditRecord) -> None:
        try:
            async with timeout(self._audit_delivery_timeout_seconds):
                await self._audit_sink.emit(record)
        except TimeoutError:
            self._logger.warning(
                "Workflow audit sink timed out",
                extra={
                    "event": WORKFLOW_AUDIT_DELIVERY_TIMEOUT,
                    "audit_delivery_timeout_seconds": self._audit_delivery_timeout_seconds,
                },
            )
        except Exception:
            self._logger.warning("Workflow audit sink failed", exc_info=True)

    async def execute(self, request: WorkflowRequest) -> WorkflowResult:
        execution_id = generate_execution_id()
        request_id = get_execution_context().request_id
        try:
            self._admission_policy.validate(request)
        except WorkflowAdmissionError as error:
            await self._emit_audit(
                WorkflowAuditRecord(
                    event=WorkflowAuditEvent.ADMISSION_REJECTED,
                    request_id=request_id,
                    execution_id=execution_id,
                    reason_code=error.code,
                    step_count=len(request.steps),
                    parallel_group_count=len(request.parallel_groups),
                )
            )
            self._logger.warning(
                "Workflow admission rejected",
                extra={
                    "event": WORKFLOW_ADMISSION_REJECTED,
                    "workflow_admission_code": error.code,
                    "workflow_step_count": len(request.steps),
                    "workflow_parallel_group_count": len(request.parallel_groups),
                },
            )
            raise
        results = []
        with bind_execution_context(capability="agent.workflows", execution_id=execution_id):
            self._logger.info(
                "Workflow execution started",
                extra={
                    "event": WORKFLOW_EXECUTION_STARTED,
                    "workflow_step_count": len(request.steps),
                    "workflow_parallel_group_count": len(request.parallel_groups),
                },
            )
            await self._emit_audit(
                WorkflowAuditRecord(
                    event=WorkflowAuditEvent.STARTED,
                    request_id=request_id,
                    execution_id=execution_id,
                    step_count=len(request.steps),
                    parallel_group_count=len(request.parallel_groups),
                )
            )
            try:
                async with timeout(request.deadline_seconds):
                    for step in request.steps:
                        results.append(await self._tool_executor.execute(step.invocation))
                    for group in request.parallel_groups:
                        if len(group) > 8:
                            raise ValueError(
                                "Parallel workflow groups cannot exceed eight children"
                            )
                        tasks = [
                            asyncio.create_task(self._tool_executor.execute(step.invocation))
                            for step in group
                        ]
                        try:
                            results.extend(await asyncio.gather(*tasks))
                        finally:
                            for task in tasks:
                                if not task.done():
                                    task.cancel()
            except TimeoutError:
                await self._emit_audit(
                    WorkflowAuditRecord(
                        event=WorkflowAuditEvent.TIMED_OUT,
                        request_id=request_id,
                        execution_id=execution_id,
                        status=WorkflowStatus.TIMED_OUT,
                        step_count=len(results),
                    )
                )
                self._logger.warning(
                    "Workflow execution timed out",
                    extra={"event": WORKFLOW_EXECUTION_TIMEOUT, "workflow_status": "timed_out"},
                )
                return WorkflowResult(status=WorkflowStatus.TIMED_OUT, steps=tuple(results))
            except asyncio.CancelledError:
                await self._emit_audit(
                    WorkflowAuditRecord(
                        event=WorkflowAuditEvent.CANCELLED,
                        request_id=request_id,
                        execution_id=execution_id,
                        status=WorkflowStatus.CANCELLED,
                        step_count=len(results),
                    )
                )
                self._logger.warning(
                    "Workflow execution cancelled",
                    extra={"event": WORKFLOW_EXECUTION_CANCELLED, "workflow_status": "cancelled"},
                )
                raise
        self._logger.info(
            "Workflow execution completed",
            extra={"event": WORKFLOW_EXECUTION_COMPLETED, "workflow_status": "completed"},
        )
        await self._emit_audit(
            WorkflowAuditRecord(
                event=WorkflowAuditEvent.COMPLETED,
                request_id=request_id,
                execution_id=execution_id,
                status=WorkflowStatus.COMPLETED,
                step_count=len(results),
            )
        )
        return WorkflowResult(status=WorkflowStatus.COMPLETED, steps=tuple(results))
