"""Validate the copyable provider-plugin template contract."""

from pathlib import Path


def test_provider_plugin_template_is_standalone_and_explicit() -> None:
    root = Path("templates/provider-plugin-example")
    assert (root / "pyproject.toml").exists()
    assert (root / "src/trussium_provider_example/chat.py").exists()
    readme = (root / "README.md").read_text()
    assert "explicitly" in readme
    assert "ChatCapability" in readme
    assert "network calls" in readme
