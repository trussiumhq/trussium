# Local Development Guide

This is the shortest supported path from a fresh checkout to a validated local
Trussium runtime. It uses Python 3.12 or newer and `uv`; no provider account,
Docker daemon, Kubernetes cluster, or hosted Trussium service is required for
the default workflow.

## Prerequisites and checkout

Install Git, Python 3.12+, and the latest `uv`, then clone the repository:

```bash
git clone https://github.com/trussiumhq/trussium.git
cd trussium
```

## Install the locked environment

`uv sync` creates or updates the project virtual environment from `uv.lock`,
including the development tools used by CI:

```bash
uv sync
```

You can activate the environment, or prefix commands with `uv run`:

```bash
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
```

Do not edit `uv.lock` manually. If dependency declarations change, run `uv
lock` and include the resulting lockfile update in the same change.

## Start without a provider

The provider-free runtime is the default safe smoke path. It exposes liveness,
readiness, capability discovery, metrics, and the CLI while rejecting inference
until a provider is configured:

```bash
uv run trussium config validate
uv run trussium serve
```

In another terminal, verify the process:

```bash
uv run trussium health --url http://127.0.0.1:9000
uv run trussium capabilities --url http://127.0.0.1:9000
curl http://127.0.0.1:9000/health/live
curl http://127.0.0.1:9000/metrics
```

Stop the foreground process with `Ctrl-C`. The default listener is loopback
port `9000`; override typed runtime settings through environment variables
rather than changing source code.

## Configure a local provider (optional)

For inference against a local Ollama-compatible server, install and start
Ollama separately, pull a model explicitly, then configure the runtime:

```bash
ollama pull llama3.1:8b
export TRUSSIUM_PROVIDER__NAME=ollama
export TRUSSIUM_PROVIDER__BASE_URL=http://127.0.0.1:11434/v1
uv run trussium config validate
uv run trussium serve
```

OpenAI-compatible gateways use `TRUSSIUM_PROVIDER__NAME=openai`, a base URL,
and a secret-injected `TRUSSIUM_PROVIDER__API_KEY`. Never commit credentials or
put them in request payloads. See [Provider Development](PROVIDER_DEVELOPMENT.md)
for adapter boundaries and [Self-Hosting](SELF_HOSTING.md) for deployment
operations.

## Run the validation ladder

Use the same fast checks as CI before opening a pull request:

```bash
uv run ruff check src tests
uv run ruff format --check .
uv run mypy src tests
uv run pytest tests/unit
uv run pytest tests/integration -m "not ollama"
```

The deterministic integration suite starts real local processes and does not
contact public providers. The live Ollama suite is opt-in only when a compatible
server and model are already installed:

```bash
TRUSSIUM_OLLAMA_TEST_MODEL=llama3.1:8b \
  uv run pytest tests/integration/test_ollama_live.py
```

For package and container contracts, use the dedicated smoke scripts described
in [Development](DEVELOPMENT.md), [Packaging](PACKAGING.md), and
[Containers](CONTAINERS.md).

## Troubleshooting

| Symptom | Action |
| --- | --- |
| `uv sync` cannot reach a package index | Retry with network access; the lockfile remains the source of truth. |
| Configuration validation fails | Run `uv run trussium config validate` and correct the named setting without exposing secrets. |
| Port 9000 is occupied | Set `TRUSSIUM_RUNTIME__PORT` to an unused local port and pass the same URL to CLI checks. |
| Readiness is healthy but chat fails | Configure a provider and model; provider-free mode intentionally rejects inference. |
| Ollama tests skip | Start the compatible server and ensure the requested model is already pulled. |
| Integration child process remains | Stop the process and rerun the deterministic suite; the harness normally cleans up every child. |

Keep generated caches, `.venv`, credentials, and local `.env` files out of
commits. The repository's `.gitignore` and CI checks enforce the expected clean
working-tree boundary.

## Contribution handoff

Before requesting review, confirm:

- [ ] The change preserves public API, SDK, and CLI contracts.
- [ ] Documentation and roadmap updates are included where workflow changed.
- [ ] Unit and deterministic integration tests pass.
- [ ] Ruff, formatting, and strict MyPy pass.
- [ ] No credentials, generated artifacts, or provider payloads are committed.
- [ ] The PR description starts with `Closes #<issue-number>` and uses the full project structure.
