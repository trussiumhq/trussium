"""Keep the self-hosted project template aligned with runtime contracts."""

from pathlib import Path

TEMPLATE = Path("templates/self-hosted-runtime")


def test_self_hosted_template_has_safe_runtime_contract() -> None:
    compose = (TEMPLATE / "compose.yaml").read_text()
    env_example = (TEMPLATE / ".env.example").read_text()
    guide = (TEMPLATE / "README.md").read_text()

    assert "ghcr.io/trussiumhq/trussium:latest" in compose
    assert '"9000:9000"' in compose
    assert "read_only: true" in compose
    assert "no-new-privileges:true" in compose
    assert "TRUSSIUM_ENVIRONMENT=production" in env_example
    assert "TRUSSIUM_PROVIDER__API_KEY" in env_example
    assert "docker compose config" in guide
    assert "Operator" in guide
