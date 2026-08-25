"""Keep core SDK links aligned with the dedicated repositories."""

from pathlib import Path


def test_sdk_guides_reference_published_packages() -> None:
    readme = Path("README.md").read_text()
    typescript = Path("docs/TYPESCRIPT_SDK.md").read_text()

    assert "trussium-sdk" in readme
    assert "github.com/trussiumhq/trussium-go" in readme
    assert "@trussium/sdk" in readme
    assert "@trussium/sdk" in typescript
    assert "npm publication is deferred" in typescript
    assert "npm run build" in typescript
