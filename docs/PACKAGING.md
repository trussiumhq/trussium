# Python Packaging Guide

Trussium produces a Python wheel and source distribution for every semantic
release. Python 3.12 or newer and [uv](https://docs.astral.sh/uv/) are required
to build or validate the packages locally.

## Package contract

The Python distribution:

- Is named `trussium` and uses the same semantic version as the Git tag.
- Requires Python 3.12 or newer.
- Declares only production runtime dependencies.
- Provides an architecture-independent `py3-none-any` wheel.
- Includes the `trussium/py.typed` marker for typed consumers.
- Includes the project README and Apache License 2.0 metadata.
- Starts through the same `python -m trussium` entry point used by source and
  container deployments.

`trussium.__version__` is read from installed distribution metadata, so it
cannot drift from the wheel or source-distribution version. A direct,
uninstalled source-tree import returns `0.0.0+unknown` when distribution
metadata is unavailable.

## Complete package validation

Run the reusable package smoke test from any working directory:

```bash
scripts/package-smoke-test.sh
```

The smoke test:

1. Builds the source distribution and builds the wheel through that source
   distribution with `uv build`.
2. Validates filenames, core metadata, Python compatibility, runtime
   dependencies, license and README metadata, wheel tags, package modules, and
   the typing marker.
3. Rejects tests, development tools, caches, bytecode, environments, build
   output, Git metadata, and unrelated repository files from the archives.
4. Installs the wheel and source distribution separately into clean Python
   3.12 virtual environments.
5. Checks installed dependency consistency and proves imports resolve from
   each isolated environment rather than the repository checkout.
6. Starts both installed runtimes on dynamically allocated loopback ports.
7. Imports and invokes the sealed-registry capability execution pipeline with
   public ordered middleware from each installed artifact.
8. Exercises liveness, readiness, component health, empty capability discovery,
   metrics, and caller-provided request correlation over real HTTP connections.
9. Sends `SIGTERM`, requires bounded shutdown, and always cleans up temporary
   processes and environments.

Hatch includes the root `.gitignore` in source distributions as a standard
build input. The validator permits that file but rejects Git repository data
and all other unrelated project files.

## Keeping local artifacts

The default smoke test uses and removes a temporary directory. Pass an absolute
output directory to retain the validated distributions:

```bash
mkdir -p dist
scripts/package-smoke-test.sh "$(pwd)/dist"
```

The resulting files are:

```text
dist/trussium-<version>-py3-none-any.whl
dist/trussium-<version>.tar.gz
```

For a build without installation and runtime validation, run:

```bash
uv build
```

## Installing a local build

Install the wheel into a clean environment:

```bash
uv venv --python 3.12 .venv-package
uv pip install --python .venv-package/bin/python \
  dist/trussium-<version>-py3-none-any.whl
.venv-package/bin/python -m trussium
```

The source distribution can be installed in the same way. uv invokes the
declared Hatchling build backend and builds a wheel from the archive.

## Continuous integration

Pull requests and pushes to `main` run a dedicated **Package Build and
Installation** job. This job executes the same smoke test used locally, making
the built distributions—not the source checkout—the validation boundary.

## Release artifacts

Python Semantic Release stamps the new version, updates the changelog, builds
the distributions, creates the tag and GitHub release, and then runs the
package smoke test against the release `dist` directory. Only after validation
succeeds does the release workflow attach the wheel and source distribution to
the GitHub release. Container publication is dispatched afterward.

The release upload configuration matches only:

```text
dist/*.whl
dist/*.tar.gz
```

Trussium does not currently publish to PyPI or another Python package registry.
Release consumers should download the desired artifact from the corresponding
GitHub Release.

## Current limitations

- Python versions below 3.12 are unsupported.
- PyPI publication and trusted publishing are not configured.
- Python artifact signing and attestations are not yet configured.
- No standalone `trussium` console-script alias is exposed; use
  `python -m trussium`.
