from trussium.observability import RuntimeMetrics


def test_runtime_metrics_render_routing_decisions() -> None:
    metrics = RuntimeMetrics()
    metrics.routing_decision(capability="chat.completions", provider="openai", outcome="success")
    rendered = metrics.render().decode()
    assert "trussium_routing_decisions_total" in rendered
    assert 'provider="openai"' in rendered
