"""Keep the self-hosted operations guide aligned with public runtime contracts."""

from pathlib import Path


def test_self_hosting_guide_references_runtime_operations_contracts() -> None:
    document = Path("docs/SELF_HOSTING.md").read_text()

    for marker in (
        "trussium config validate",
        "trussium serve",
        "/health/live",
        "/health/ready",
        "/metrics",
        "templates/self-hosted-runtime",
        "docker compose config",
        "docker compose up -d",
        "KUBERNETES.md",
        "trussium-operator",
    ):
        assert marker in document
