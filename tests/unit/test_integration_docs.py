"""Keep the application integration guide aligned with public boundaries."""

from pathlib import Path


def test_integration_guide_covers_all_supported_surfaces() -> None:
    document = Path("docs/INTEGRATION.md").read_text()

    for marker in (
        "/health/ready",
        "/v1/chat/completions",
        "Python SDK",
        "Go SDK",
        "TypeScript SDK",
        "X-Request-ID",
        "Server-Sent Events",
        "trussium-operator",
        "PROVIDER_DEVELOPMENT.md",
        "CAPABILITY_DEVELOPMENT.md",
    ):
        assert marker in document
