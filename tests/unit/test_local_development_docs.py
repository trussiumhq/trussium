"""Keep the local development guide aligned with supported tooling."""

from pathlib import Path


def test_local_development_guide_covers_supported_workflow() -> None:
    document = Path("docs/LOCAL_DEVELOPMENT.md").read_text()

    for marker in (
        "Python 3.12",
        "uv sync",
        "trussium config validate",
        "trussium serve",
        "trussium health",
        "TRUSSIUM_PROVIDER__NAME",
        "uv run ruff check src tests",
        "uv run mypy src tests",
        'uv run pytest tests/integration -m "not ollama"',
        "Closes #<issue-number>",
    ):
        assert marker in document
