from trussium.runtime import (
    AuditTrail,
    ExecutionContext,
    reset_execution_context,
    set_execution_context,
)


def test_audit_trail_records_attribution_and_bounds_events() -> None:
    trail = AuditTrail(max_events=1)
    token = set_execution_context(
        ExecutionContext(request_id="req-1", execution_id="exec-1", tenant_id="tenant-1")
    )
    try:
        trail.record(method="POST", path="/v1/chat/completions", status_code=200, outcome="success")
    finally:
        reset_execution_context(token)
    trail.record(method="GET", path="/v1/models", status_code=401, outcome="rejected")

    event = trail.snapshot()[0]
    assert event.path == "/v1/models"
    assert event.status_code == 401
    assert event.tenant_id is None
