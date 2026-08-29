"""Bounded privacy-safe audit records."""

from dataclasses import dataclass
from time import time

from trussium.runtime.context import get_execution_context


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """One request-attribution record without payload or credential data."""

    timestamp: float
    request_id: str | None
    execution_id: str | None
    tenant_id: str | None
    project_id: str | None
    application_id: str | None
    method: str
    path: str
    status_code: int | None
    outcome: str


class AuditTrail:
    """Retain a bounded process-local audit event snapshot."""

    def __init__(self, *, max_events: int = 10_000) -> None:
        self._max_events = max_events
        self._events: list[AuditEvent] = []

    def record(self, *, method: str, path: str, status_code: int | None, outcome: str) -> None:
        """Record request attribution from the active execution context."""
        context = get_execution_context()
        if len(self._events) >= self._max_events:
            self._events.pop(0)
        self._events.append(
            AuditEvent(
                timestamp=time(),
                request_id=context.request_id,
                execution_id=context.execution_id,
                tenant_id=context.tenant_id,
                project_id=context.project_id,
                application_id=context.application_id,
                method=method,
                path=path,
                status_code=status_code,
                outcome=outcome,
            )
        )

    def snapshot(self) -> tuple[AuditEvent, ...]:
        """Return an immutable copy of retained audit events."""
        return tuple(self._events)
