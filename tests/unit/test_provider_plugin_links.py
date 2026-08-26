"""Keep the core provider guide linked to standalone community adapters."""

from pathlib import Path


def test_provider_guide_links_first_community_adapter() -> None:
    document = Path("docs/PROVIDER_DEVELOPMENT.md").read_text()

    assert "trussium-provider-vllm" in document
    assert "self-hosted vLLM" in document
    assert "does not install, configure, or manage vLLM" in document
    assert "trussium-provider-anthropic" in document
    assert "managed-provider adapter" in document
    assert "does not store credentials" in document
