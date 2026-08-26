"""Keep the plugin development guide aligned with ADR-0004 boundaries."""

from pathlib import Path


def test_plugin_development_guide_covers_safe_current_boundary() -> None:
    document = Path("docs/PLUGIN_DEVELOPMENT.md").read_text()

    for marker in (
        "ADR-0004",
        "not dynamically loaded",
        "CapabilityMiddleware",
        "RuntimeServiceRegistry",
        "registry.seal()",
        "trust",
        "compatibility",
        "importlib",
        "uv run pytest",
        "credentials",
    ):
        assert marker in document
