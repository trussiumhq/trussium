"""Static contracts for portable runtime alerting guidance."""

import re
from pathlib import Path
from typing import Any, cast

import yaml

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_RULES_PATH = (
    _REPOSITORY_ROOT
    / "deploy"
    / "observability"
    / "prometheus"
    / "rules"
    / "trussium-runtime-alerts.yaml"
)
_TESTS_PATH = (
    _REPOSITORY_ROOT / "tests" / "fixtures" / "prometheus" / ("trussium-runtime-alerts.test.yaml")
)
_EXPECTED_ALERTS = {
    "TrussiumRuntimeTelemetryMissing": "warning",
    "TrussiumRuntimeRequestFailuresHigh": "critical",
    "TrussiumRuntimeRequestCancellationsHigh": "warning",
    "TrussiumRuntimeRequestLatencyHigh": "warning",
    "TrussiumRuntimeProcessRestarted": "warning",
}


def _load_yaml(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return cast(dict[str, Any], loaded)


def _rules() -> list[dict[str, Any]]:
    document = _load_yaml(_RULES_PATH)
    groups = cast(list[dict[str, Any]], document["groups"])
    assert len(groups) == 1
    assert groups[0]["name"] == "trussium-runtime"
    assert groups[0]["interval"] == "30s"
    return cast(list[dict[str, Any]], groups[0]["rules"])


def test_alert_profile_has_stable_identity_severity_and_runbooks() -> None:
    """Every starter alert should identify an actionable documented condition."""
    rules = _rules()

    assert {cast(str, rule["alert"]) for rule in rules} == set(_EXPECTED_ALERTS)
    for rule in rules:
        alert = cast(str, rule["alert"])
        labels = cast(dict[str, str], rule["labels"])
        annotations = cast(dict[str, str], rule["annotations"])

        assert labels == {"severity": _EXPECTED_ALERTS[alert], "component": "runtime"}
        assert set(annotations) == {"summary", "description", "runbook_url"}
        assert annotations["summary"].startswith("Trussium ")
        assert annotations["description"].endswith(".")
        assert annotations["runbook_url"] == (
            f"https://github.com/trussiumhq/trussium/blob/main/docs/ALERTING.md#{alert.lower()}"
        )


def test_alert_queries_use_only_bounded_runtime_contracts() -> None:
    """PromQL should preserve the existing metric and label privacy boundary."""
    expressions = {cast(str, rule["alert"]): cast(str, rule["expr"]) for rule in _rules()}
    joined = "\n".join(expressions.values())
    metric_names = set(re.findall(r"(?:trussium|process)_[a-z_]+", joined))

    assert metric_names == {
        "trussium_http_requests_active",
        "trussium_http_requests_total",
        "trussium_http_request_duration_seconds_bucket",
        "process_start_time_seconds",
    }
    assert all(
        sensitive not in joined
        for sensitive in (
            "path",
            "request_id",
            "execution_id",
            "trace_id",
            "span_id",
            "provider",
            "model",
            "tenant",
        )
    )
    assert 'outcome="failed"' in expressions["TrussiumRuntimeRequestFailuresHigh"]
    assert 'outcome="cancelled"' in expressions["TrussiumRuntimeRequestCancellationsHigh"]
    assert "histogram_quantile(" in expressions["TrussiumRuntimeRequestLatencyHigh"]
    assert "0.95" in expressions["TrussiumRuntimeRequestLatencyHigh"]
    assert (
        "changes(process_start_time_seconds[15m])" in expressions["TrussiumRuntimeProcessRestarted"]
    )


def test_ratio_and_latency_alerts_guard_minimum_traffic() -> None:
    """Statistical alerts should stay inactive for idle and tiny workloads."""
    statistical_alerts = {
        "TrussiumRuntimeRequestFailuresHigh": ("0.05", "10m"),
        "TrussiumRuntimeRequestCancellationsHigh": ("0.10", "15m"),
        "TrussiumRuntimeRequestLatencyHigh": ("> 5", "10m"),
    }
    by_name = {cast(str, rule["alert"]): rule for rule in _rules()}

    for alert, (threshold, hold) in statistical_alerts.items():
        rule = by_name[alert]
        expression = cast(str, rule["expr"])
        assert threshold in expression
        assert "rate(trussium_http_requests_total[5m])" in expression
        assert "> 0.1" in expression
        assert rule["for"] == hold


def test_promtool_scenarios_cover_each_alert_and_low_traffic() -> None:
    """Synthetic semantic tests should exercise every starter rule."""
    document = _load_yaml(_TESTS_PATH)
    scenarios = cast(list[dict[str, Any]], document["tests"])
    tested_alerts = {
        cast(str, test["alertname"])
        for scenario in scenarios
        for test in cast(list[dict[str, Any]], scenario["alert_rule_test"])
    }

    assert tested_alerts == set(_EXPECTED_ALERTS)
    assert any("low traffic" in cast(str, scenario["name"]) for scenario in scenarios)
    assert document["evaluation_interval"] == "1m"


def test_runbook_covers_every_alert_and_operational_pivot() -> None:
    """Every rule should resolve to complete, privacy-aware operator guidance."""
    guide = (_REPOSITORY_ROOT / "docs" / "ALERTING.md").read_text(encoding="utf-8")

    for alert in _EXPECTED_ALERTS:
        assert f"## {alert}" in guide

    for event in (
        "runtime.configuration.invalid",
        "provider.configuration.unavailable",
        "runtime.shutdown.drain_timeout",
        "runtime.shutdown.cleanup_timeout",
        "observability.trace_export.failed",
        "observability.tracing.shutdown.failed",
        "runtime.stopped",
        "runtime.shutdown.completed",
    ):
        assert f"`{event}`" in guide

    assert "not a universal\nservice-level objective or paging policy" in guide
    assert "Loki and Tempo are diagnostic aids, not dependencies" in guide
    assert "request, execution, trace, model, or\nprovider identifiers" in guide
    assert "Readiness dependency checks\nremain a separate roadmap item" in guide


def test_alert_artifacts_stay_out_of_runtime_packages_and_deployments() -> None:
    """Guidance should not silently become a runtime or Kubernetes install surface."""
    dockerignore = (_REPOSITORY_ROOT / ".dockerignore").read_text(encoding="utf-8")
    project = (_REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    kustomization = (
        _REPOSITORY_ROOT / "deploy" / "kubernetes" / "base" / "kustomization.yaml"
    ).read_text(encoding="utf-8")

    assert "!deploy/" not in dockerignore
    assert '"/deploy"' not in project
    assert "PrometheusRule" not in kustomization
    assert "AlertmanagerConfig" not in kustomization


def test_pinned_promtool_validation_runs_in_ci() -> None:
    """Syntax and semantics should be validated by a real immutable tool image."""
    script_path = _REPOSITORY_ROOT / "scripts" / "alert-rules-smoke-test.sh"
    script = script_path.read_text(encoding="utf-8")
    workflow = (_REPOSITORY_ROOT / ".github" / "workflows" / "ci.yaml").read_text(encoding="utf-8")

    assert script_path.stat().st_mode & 0o100
    assert (
        'image="prom/prometheus:v3.6.0@sha256:'
        '76947e7ef22f8a698fc638f706685909be425dbe09bd7a2cd7aca849f79b5f64"' in script
    )
    assert "--read-only" in script
    assert "--tmpfs /tmp:rw,noexec,nosuid,size=32m" in script
    assert "--network none" in script
    assert "--cap-drop ALL" in script
    assert 'run_promtool check rules "$rules"' in script
    assert 'run_promtool test rules "$tests"' in script
    assert "scripts/alert-rules-smoke-test.sh" in workflow
