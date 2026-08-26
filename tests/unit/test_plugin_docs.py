"""Keep the provider-plugin architecture boundary explicit and consistent."""

from pathlib import Path


def test_plugin_docs_require_explicit_registration_and_trust_boundary() -> None:
    guide = Path("docs/PLUGIN_DEVELOPMENT.md").read_text()
    provider_guide = Path("docs/PROVIDER_DEVELOPMENT.md").read_text()
    adr = Path("docs/adr/0008-community-provider-plugin-boundary.md").read_text()

    for document in (guide, provider_guide, adr):
        assert "explicit" in document.lower()
        assert "dynamic" in document.lower() or "loader" in document.lower()

    assert "ADR-0008" in guide
    assert "application-owned" in guide
    assert "fail closed" in adr
