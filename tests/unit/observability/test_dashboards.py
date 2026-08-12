"""Static contracts for portable Grafana runtime dashboards."""

import json
import re
from pathlib import Path
from typing import Any, cast

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_DASHBOARD_ROOT = _REPOSITORY_ROOT / "deploy" / "observability" / "grafana" / "dashboards"

_DASHBOARDS = {
    "trussium-runtime-overview.json": (
        "trussium-runtime-overview",
        "Trussium Runtime Overview",
        "prometheus",
        "prometheus",
    ),
    "trussium-runtime-logs.json": (
        "trussium-runtime-logs",
        "Trussium Runtime Logs",
        "loki",
        "loki",
    ),
    "trussium-runtime-traces.json": (
        "trussium-runtime-traces",
        "Trussium Runtime Traces",
        "tempo",
        "tempo",
    ),
}


def _load_dashboard(name: str) -> dict[str, Any]:
    loaded = json.loads((_DASHBOARD_ROOT / name).read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return cast(dict[str, Any], loaded)


def _panel_by_title(dashboard: dict[str, Any], title: str) -> dict[str, Any]:
    panels = cast(list[dict[str, Any]], dashboard["panels"])
    return next(panel for panel in panels if panel["title"] == title)


def _expressions(dashboard: dict[str, Any]) -> list[str]:
    panels = cast(list[dict[str, Any]], dashboard["panels"])
    return [
        cast(str, target[key])
        for panel in panels
        for target in cast(list[dict[str, Any]], panel.get("targets", []))
        for key in ("expr", "query")
        if key in target
    ]


def test_dashboards_have_stable_identity_and_portable_datasources() -> None:
    """Every dashboard should import independently against a selected backend."""
    assert {path.name for path in _DASHBOARD_ROOT.glob("*.json")} == set(_DASHBOARDS)

    for name, (uid, title, variable_name, datasource_type) in _DASHBOARDS.items():
        dashboard = _load_dashboard(name)
        variables = cast(list[dict[str, Any]], dashboard["templating"]["list"])
        panels = cast(list[dict[str, Any]], dashboard["panels"])

        assert dashboard["uid"] == uid
        assert dashboard["title"] == title
        assert dashboard["schemaVersion"] == 41
        assert dashboard["version"] == 1
        assert dashboard["refresh"] == "30s"
        assert {"trussium", "runtime", datasource_type} <= set(dashboard["tags"])
        assert variables[0]["name"] == variable_name
        assert variables[0]["type"] == "datasource"
        assert variables[0]["query"] == datasource_type
        assert len(panels) >= 6

        data_panels = [panel for panel in panels if panel["type"] != "text"]
        assert all(
            panel["datasource"] == {"type": datasource_type, "uid": f"${{{variable_name}}}"}
            for panel in data_panels
        )


def test_dashboards_do_not_embed_connections_credentials_or_alerts() -> None:
    """Artifacts should remain backend-neutral and should not become secret stores."""
    forbidden = (
        "127.0.0.1",
        "localhost",
        "authorization",
        "api_key",
        "password",
        "client_secret",
        '"alert":',
        '"alertlist"',
    )

    for path in _DASHBOARD_ROOT.glob("*.json"):
        raw = path.read_text(encoding="utf-8").lower()
        assert all(value not in raw for value in forbidden)


def test_overview_uses_the_documented_bounded_metrics_contract() -> None:
    """PromQL should use only stable metrics and low-cardinality dimensions."""
    dashboard = _load_dashboard("trussium-runtime-overview.json")
    expressions = _expressions(dashboard)
    joined = "\n".join(expressions)
    panel_titles = {panel["title"] for panel in dashboard["panels"]}
    metric_names = set(re.findall(r"(?:trussium|process)_[a-z_]+", joined))

    assert {
        "Request rate",
        "Active work",
        "Success rate",
        "Failed/cancelled",
        "End-to-end request latency",
        "Request rate by outcome",
        "HTTP status distribution",
        "Request rate by method",
        "Process CPU usage",
        "Process resident memory",
        "Process uptime",
    } == panel_titles
    assert metric_names == {
        "trussium_http_requests_active",
        "trussium_http_requests_total",
        "trussium_http_request_duration_seconds_bucket",
        "process_cpu_seconds_total",
        "process_resident_memory_bytes",
        "process_start_time_seconds",
    }
    assert all('job=~"$job"' in expression for expression in expressions)
    assert all('instance=~"$instance"' in expression for expression in expressions)
    assert all(
        sensitive not in joined
        for sensitive in ("path=", "request_id", "execution_id", "trace_id", "provider", "model")
    )

    latency_targets = cast(
        list[dict[str, Any]], _panel_by_title(dashboard, "End-to-end request latency")["targets"]
    )
    latency_expressions = [cast(str, target["expr"]) for target in latency_targets]
    assert [target["legendFormat"] for target in latency_targets] == ["p50", "p95", "p99"]
    assert all("sum by (le)" in expression for expression in latency_expressions)
    assert [
        quantile
        for quantile in ("0.50", "0.95", "0.99")
        if f"histogram_quantile({quantile}" in "\n".join(latency_expressions)
    ] == ["0.50", "0.95", "0.99"]


def test_logs_dashboard_surfaces_the_operational_event_contract() -> None:
    """LogQL panels should cover lifecycle, readiness, and failure diagnosis."""
    dashboard = _load_dashboard("trussium-runtime-logs.json")
    expressions = _expressions(dashboard)
    joined = "\n".join(expressions)
    titles = {panel["title"] for panel in dashboard["panels"]}

    assert titles == {
        "Operational error events",
        "Provider configuration state",
        "Runtime lifecycle",
        "Execution failures and cancellations",
        "Operational failure detail",
        "Structured event stream",
    }
    assert all('{job=~"$job",instance=~"$instance"}' in query for query in expressions)
    assert "| json" in joined
    assert r"runtime\.(configuration\..+|started|stopping|stopped|shutdown\..+)" in joined
    assert r"provider\.configuration\.(ready|unavailable)" in joined
    assert (
        r"(http\.request|capability\.execution|provider\.execution)\.(failed|cancelled)" in joined
    )
    assert r"observability\.trace_export\.failed" in joined
    assert all(
        sensitive not in joined.lower()
        for sensitive in ("prompt", "completion", "request_body", "authorization", "api_key")
    )


def test_traces_dashboard_preserves_runtime_span_hierarchy() -> None:
    """TraceQL should expose HTTP, capability, and provider execution spans."""
    dashboard = _load_dashboard("trussium-runtime-traces.json")
    expressions = _expressions(dashboard)
    joined = "\n".join(expressions)
    titles = {panel["title"] for panel in dashboard["panels"]}

    assert titles == {
        "Trace investigation contract",
        "Recent Trussium traces",
        "Failed traces",
        "Slow traces",
        "HTTP server spans",
        "Capability spans",
        "Provider client spans",
    }
    assert all('resource.service.name = "$service"' in query for query in expressions)
    assert 'name = "HTTP POST"' in joined
    assert 'name = "trussium.capability.chat"' in joined
    assert 'name = "trussium.provider.chat"' in joined
    assert "status = error" in joined
    assert "duration > $slow_threshold" in joined
    assert "kind = server" in joined
    assert "kind = internal" in joined
    assert "kind = client" in joined


def test_grafana_import_smoke_test_is_pinned_and_runs_in_ci() -> None:
    """A real pinned Grafana should provision all tracked dashboard models."""
    script_path = _REPOSITORY_ROOT / "scripts" / "dashboard-smoke-test.sh"
    script = script_path.read_text(encoding="utf-8")
    workflow = (_REPOSITORY_ROOT / ".github" / "workflows" / "ci.yaml").read_text(encoding="utf-8")

    assert script_path.stat().st_mode & 0o100
    assert (
        'image="grafana/grafana:12.2.0@sha256:'
        '74144189b38447facf737dfd0f3906e42e0776212bf575dc3334c3609183adf7"' in script
    )
    assert "/api/dashboards/uid/${uid}" in script
    assert "trussium-runtime-overview" in script
    assert "trussium-runtime-logs" in script
    assert "trussium-runtime-traces" in script
    assert "dashboard-smoke-test.sh" in workflow
