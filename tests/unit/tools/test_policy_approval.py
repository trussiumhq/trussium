from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from trussium.tools import (
    ToolApprovalDecision,
    ToolApprovalRequest,
    ToolApprovalResult,
    ToolAuthorizationDecision,
    ToolAuthorizationRequest,
    ToolAuthorizationResult,
)


def test_authorization_request_is_immutable_and_payload_free() -> None:
    request = ToolAuthorizationRequest(
        identity="user-1",
        tool_name="search",
        tool_version="1.0.0",
        deadline_seconds=5,
    )
    with pytest.raises(ValidationError):
        ToolAuthorizationRequest(
            identity="user-1",
            tool_name="search",
            tool_version="1.0.0",
            deadline_seconds=5,
            arguments={"secret": "value"},  # type: ignore[call-arg]
        )
    with pytest.raises(ValidationError):
        request.deadline_seconds = 1


def test_authorization_result_has_stable_decision_and_reason() -> None:
    result = ToolAuthorizationResult(
        decision=ToolAuthorizationDecision.APPROVAL_REQUIRED,
        reason_code="sensitive_operation",
    )
    assert result.decision == "approval_required"


def test_approval_request_requires_bounded_expiry_metadata() -> None:
    now = datetime.now(UTC)
    request = ToolApprovalRequest(
        request_id="approval-1",
        parent_execution_id="execution-1",
        tool_name="search",
        tool_version="1.0.0",
        identity="user-1",
        created_at=now,
        expires_at=now + timedelta(seconds=10),
        reason_code="sensitive_operation",
    )
    assert request.model_config["frozen"] is True


def test_approval_result_is_terminal_and_stable() -> None:
    result = ToolApprovalResult(
        decision=ToolApprovalDecision.EXPIRED,
        reason_code="approval_timed_out",
    )
    assert result.decision == "expired"
