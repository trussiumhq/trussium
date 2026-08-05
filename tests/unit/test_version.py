from importlib import metadata

import trussium


def test_runtime_version_matches_distribution_metadata() -> None:
    assert trussium.__version__ == metadata.version("trussium")


def test_runtime_version_has_source_tree_fallback() -> None:
    def missing_distribution(_distribution_name: str) -> str:
        raise metadata.PackageNotFoundError

    assert trussium._get_version(missing_distribution) == "0.0.0+unknown"
