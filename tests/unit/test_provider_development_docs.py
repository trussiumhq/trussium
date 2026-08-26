"""Keep the provider development guide aligned with implementation contracts."""

from pathlib import Path


def test_provider_development_guide_covers_extension_boundaries() -> None:
    document = Path("docs/PROVIDER_DEVELOPMENT.md").read_text()

    for marker in (
        "ChatCapability",
        "CapabilityExecutionError",
        "TRUSSIUM_PROVIDER__API_KEY",
        "UPSTREAM_TIMEOUT",
        "streaming",
        "uv run mypy src tests",
        "provider\nregistry",
        "plugin-development milestones",
    ):
        assert marker in document
