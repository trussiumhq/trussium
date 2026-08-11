"""Tests for application-scoped runtime metric instruments."""

from pathlib import Path

from prometheus_client.parser import text_string_to_metric_families

from trussium.observability import RuntimeMetrics


def metric_samples(metrics: RuntimeMetrics) -> dict[str, float]:
    """Return rendered samples keyed by their complete sample name."""
    return {
        sample.name: sample.value
        for family in text_string_to_metric_families(metrics.render().decode())
        for sample in family.samples
        if not sample.labels
    }


def metric_sample_names(metrics: RuntimeMetrics) -> set[str]:
    """Return every rendered sample name, including labeled samples."""
    return {
        sample.name
        for family in text_string_to_metric_families(metrics.render().decode())
        for sample in family.samples
    }


def test_registry_exposes_runtime_python_and_process_metrics() -> None:
    metrics = RuntimeMetrics()

    samples = metric_samples(metrics)
    sample_names = metric_sample_names(metrics)

    assert samples["trussium_http_requests_active"] == 0
    assert "python_info" in sample_names
    if Path("/proc/self/stat").is_file():
        assert "process_start_time_seconds" in sample_names


def test_request_lifecycle_updates_bounded_metric_series() -> None:
    metrics = RuntimeMetrics()

    metrics.request_started()
    assert metric_samples(metrics)["trussium_http_requests_active"] == 1

    metrics.request_finished(
        method="POST",
        outcome="completed",
        status_code=200,
        duration_seconds=0.25,
    )

    rendered = metrics.render().decode()
    assert (
        'trussium_http_requests_total{method="POST",outcome="completed",status_code="200"} 1.0'
    ) in rendered
    assert (
        'trussium_http_request_duration_seconds_count{method="POST",outcome="completed"} 1.0'
    ) in rendered
    assert (
        'trussium_http_request_duration_seconds_sum{method="POST",outcome="completed"} 0.25'
    ) in rendered
    assert metric_samples(metrics)["trussium_http_requests_active"] == 0
