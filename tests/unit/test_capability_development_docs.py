"""Keep the capability development guide aligned with public contracts."""

from pathlib import Path


def test_capability_development_guide_covers_composition_boundaries() -> None:
    document = Path("docs/CAPABILITY_DEVELOPMENT.md").read_text()

    for marker in (
        "ChatCapability",
        "CapabilityMetadata",
        "CapabilityRegistry",
        "CapabilityExecutionPipeline",
        "CAPABILITY_AVAILABILITY.md",
        "CAPABILITY_LIFECYCLE.md",
        "streaming",
        "uv run pytest tests/unit/capabilities",
        "provider\nregistries",
    ):
        assert marker in document
