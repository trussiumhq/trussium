"""Bounded execution of declared in-process tools."""

from asyncio import timeout
from datetime import UTC, datetime, timedelta
from math import isfinite

from trussium.observability import (
    TOOL_APPROVAL_DECIDED,
    TOOL_APPROVAL_EXPIRED,
    TOOL_APPROVAL_REQUESTED,
    TOOL_AUTHORIZATION_DECIDED,
    TOOL_AUTHORIZATION_REQUESTED,
    TOOL_EXECUTION_COMPLETED,
    TOOL_EXECUTION_FAILED,
    TOOL_EXECUTION_STARTED,
    TOOL_EXECUTION_TIMEOUT,
    get_logger,
)
from trussium.observability.metrics import RuntimeMetrics
from trussium.runtime import bind_execution_context, generate_execution_id, get_execution_context
from trussium.tools.approval import (
    ToolApprovalAdapter,
    ToolApprovalDecision,
    ToolApprovalRequest,
    ToolApprovalResult,
    ToolApprovalTimeoutError,
)
from trussium.tools.contracts import ToolExecutionResult, ToolInvocation
from trussium.tools.policy import (
    ToolAuthorizationDecision,
    ToolAuthorizationError,
    ToolAuthorizationRequest,
    ToolAuthorizationResult,
    ToolPolicyAdapter,
)
from trussium.tools.registry import ToolRegistry


class ToolExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        *,
        timeout_seconds: float = 10.0,
        policy_adapter: ToolPolicyAdapter | None = None,
        approval_adapter: ToolApprovalAdapter | None = None,
        approval_timeout_seconds: float = 10.0,
        metrics: RuntimeMetrics | None = None,
    ) -> None:
        if not isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("Tool execution timeout must be finite and positive")
        if not isfinite(approval_timeout_seconds) or approval_timeout_seconds <= 0:
            raise ValueError("Tool approval timeout must be finite and positive")
        self._registry = registry
        self._timeout_seconds = timeout_seconds
        self._policy_adapter = policy_adapter
        self._approval_adapter = approval_adapter
        self._approval_timeout_seconds = approval_timeout_seconds
        self._metrics = metrics
        self._logger = get_logger("tools.execution")

    @property
    def registry(self) -> ToolRegistry:
        """Return the application-owned tool registry."""
        return self._registry

    async def execute(self, invocation: ToolInvocation) -> ToolExecutionResult:
        tool = self._registry.require(invocation.name)
        context = get_execution_context()
        execution_id = context.execution_id or generate_execution_id()
        with bind_execution_context(capability="tools.executions", execution_id=execution_id):
            self._logger.info(
                "Tool execution started",
                extra={"event": TOOL_EXECUTION_STARTED, "tool_name": tool.name},
            )
            try:
                if self._policy_adapter is not None:
                    self._logger.info(
                        "Tool authorization requested",
                        extra={"event": TOOL_AUTHORIZATION_REQUESTED, "tool_name": tool.name},
                    )
                    policy_result = await self._authorize(tool.name, tool.version)
                    self._logger.info(
                        "Tool authorization decided",
                        extra={
                            "event": TOOL_AUTHORIZATION_DECIDED,
                            "tool_name": tool.name,
                            "outcome": policy_result.decision.value,
                        },
                    )
                    if self._metrics is not None:
                        self._metrics.tool_authorization_decision(
                            decision=policy_result.decision.value
                        )
                    if policy_result.decision is ToolAuthorizationDecision.DENY:
                        raise ToolAuthorizationError(policy_result.reason_code)
                    if policy_result.decision is ToolAuthorizationDecision.APPROVAL_REQUIRED:
                        if self._approval_adapter is None:
                            raise ToolAuthorizationError("approval_adapter_unavailable")
                        approval_request = ToolApprovalRequest(
                            request_id=context.request_id or execution_id,
                            parent_execution_id=execution_id,
                            tool_name=tool.name,
                            tool_version=tool.version,
                            identity=context.application_id or "anonymous",
                            created_at=datetime.now(UTC),
                            expires_at=datetime.now(UTC)
                            + timedelta(seconds=self._approval_timeout_seconds),
                            reason_code=policy_result.reason_code,
                        )
                        self._logger.info(
                            "Tool approval requested",
                            extra={"event": TOOL_APPROVAL_REQUESTED, "tool_name": tool.name},
                        )
                        approval_result = await self._approve(approval_request)
                        self._logger.info(
                            "Tool approval decided",
                            extra={
                                "event": TOOL_APPROVAL_DECIDED,
                                "tool_name": tool.name,
                                "outcome": approval_result.decision.value,
                            },
                        )
                        if self._metrics is not None:
                            self._metrics.tool_approval_decision(
                                decision=approval_result.decision.value
                            )
                        if approval_result.decision is not ToolApprovalDecision.APPROVED:
                            raise ToolAuthorizationError(approval_result.reason_code)
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

    async def _authorize(self, tool_name: str, tool_version: str) -> ToolAuthorizationResult:
        context = get_execution_context()
        request = ToolAuthorizationRequest(
            request_id=context.request_id,
            execution_id=context.execution_id,
            identity=context.application_id or "anonymous",
            tenant_id=context.tenant_id,
            tool_name=tool_name,
            tool_version=tool_version,
            capability=context.capability,
            provider=context.provider,
            model=context.model,
            deadline_seconds=self._timeout_seconds,
        )
        async with timeout(self._timeout_seconds):
            return await self._policy_adapter.authorize(request)  # type: ignore[union-attr]

    async def _approve(self, request: ToolApprovalRequest) -> ToolApprovalResult:
        try:
            async with timeout(self._approval_timeout_seconds):
                return await self._approval_adapter.request_approval(request)  # type: ignore[union-attr]
        except TimeoutError as error:
            self._logger.warning(
                "Tool approval expired",
                extra={"event": TOOL_APPROVAL_EXPIRED, "tool_name": request.tool_name},
            )
            raise ToolApprovalTimeoutError() from error
