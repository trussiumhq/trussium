"""Keep public API examples aligned with stable runtime entry points."""

from pathlib import Path


def test_api_usage_examples_reference_public_runtime_contracts() -> None:
    document = Path("docs/API_USAGE.md").read_text()

    assert "trussium serve" in document
    assert "/health/ready" in document
    assert "/v1/capabilities/availability" in document
    assert "/v1/chat/completions" in document
    assert "from trussium_sdk import TrussiumClient" in document
