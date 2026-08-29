from collections.abc import Mapping

import pytest

from trussium.runtime import (
    ExecutionContext,
    UsageMeter,
    UsageQuotaExceededError,
    UsageSnapshot,
    reset_execution_context,
    set_execution_context,
)


def test_usage_meter_aggregates_tokens_by_identity() -> None:
    meter = UsageMeter(max_identities=2)
    token = set_execution_context(
        ExecutionContext(tenant_id="tenant-1", project_id="project-1", application_id="app-1")
    )
    try:
        meter.record(input_tokens=2, output_tokens=3, total_tokens=5)
        meter.record()
    finally:
        reset_execution_context(token)

    snapshot = meter.snapshot()["tenant-1:project-1:app-1"]
    assert snapshot.requests == 2
    assert snapshot.input_tokens == 2
    assert snapshot.output_tokens == 3
    assert snapshot.total_tokens == 5


def test_usage_meter_bounds_identity_cardinality() -> None:
    meter = UsageMeter(max_identities=1)
    token = set_execution_context(ExecutionContext(tenant_id="tenant-1"))
    try:
        meter.record()
    finally:
        reset_execution_context(token)
    token = set_execution_context(ExecutionContext(tenant_id="tenant-2"))
    try:
        meter.record()
    finally:
        reset_execution_context(token)

    assert set(meter.snapshot()) == {"tenant-1:-:-"}


def test_usage_meter_enforces_token_quota() -> None:
    meter = UsageMeter(max_tokens=10)
    meter.record(input_tokens=4, output_tokens=5, total_tokens=9)
    with pytest.raises(UsageQuotaExceededError):
        meter.record(total_tokens=2)


def test_usage_exporter_receives_immutable_snapshots_and_failures_are_isolated() -> None:
    class Exporter:
        def __init__(self) -> None:
            self.snapshots: list[Mapping[str, UsageSnapshot]] = []

        def export(self, snapshot: Mapping[str, UsageSnapshot]) -> None:
            self.snapshots.append(snapshot)
            if len(self.snapshots) == 2:
                raise RuntimeError("export unavailable")

    exporter = Exporter()
    meter = UsageMeter(exporter=exporter)
    meter.record()
    meter.record()

    assert len(exporter.snapshots) == 2
    assert dict(exporter.snapshots[0]) == {"-:-:-": UsageSnapshot(requests=1)}
