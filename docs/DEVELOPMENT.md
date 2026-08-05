# Development Guide

This guide explains how to set up a local development environment for Trussium.

It is intended for contributors working on the runtime and related components.

---

# Prerequisites

The following tools are required.

| Tool | Version |
|------|---------|
| Python | 3.12+ |
| Git | Latest |
| uv | Latest |

---

# Clone the Repository

```bash
git clone https://github.com/trussium/trussium-runtime.git

cd trussium-runtime
```

---

# Install Dependencies

Install project dependencies using uv.

```bash
uv sync
```

---

# Activate the Virtual Environment

```bash
source .venv/bin/activate
```

Windows (PowerShell):

```powershell
.venv\Scripts\Activate.ps1
```

Alternatively, most commands can be executed directly using `uv run` without activating the virtual environment.

---

# Running the Application

Start the runtime.

```bash
uv run python -m trussium
```

Without provider credentials, the runtime starts with health endpoints while
the chat endpoint reports that no provider is configured.

The production entry point drains active requests and SSE streams for 30
seconds after `SIGTERM` by default. Override the positive whole-number deadline
with `TRUSSIUM_RUNTIME__GRACEFUL_SHUTDOWN_SECONDS`. See the
[Graceful Shutdown Guide](SHUTDOWN.md) for lifecycle semantics, deployment
timing, correlated cancellation logs, and deterministic process validation.

## OpenAI provider

Existing OpenAI deployments can continue to use the OpenAI SDK environment
contract.

```bash
export OPENAI_API_KEY="your-openai-api-key"
uv run python -m trussium
```

An OpenAI-compatible gateway can also be selected with
`OPENAI_BASE_URL`. Trussium's typed provider settings take precedence when
both forms are present:

```bash
export TRUSSIUM_PROVIDER__NAME="openai"
export TRUSSIUM_PROVIDER__BASE_URL="https://api.openai.com/v1"
export TRUSSIUM_PROVIDER__API_KEY="your-openai-api-key"
uv run python -m trussium
```

## Ollama provider

Trussium supports Ollama through its OpenAI-compatible Responses API. Ollama
0.13.3 or newer is required because that release introduced `/v1/responses`.
Compatibility is currently validated against Ollama 0.32.5.

Install and start Ollama, then pull a model explicitly. Trussium and its test
suite never download models automatically.

```bash
ollama pull llama3.1:8b
```

Select Ollama and start Trussium on its standard port. The local Ollama URL
defaults to `http://127.0.0.1:11434/v1`, and no credential is required for a
default local installation.

```bash
export TRUSSIUM_PROVIDER__NAME="ollama"
uv run python -m trussium
```

Send the same normalized request used for a managed provider:

```bash
curl http://127.0.0.1:9000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.1:8b",
    "messages": [
      {"role": "user", "content": "Say hello in one sentence."}
    ],
    "stream": false
  }'
```

For a remote Ollama-compatible endpoint or authenticated gateway, configure
the URL and credential explicitly:

```bash
export TRUSSIUM_PROVIDER__NAME="ollama"
export TRUSSIUM_PROVIDER__BASE_URL="https://ollama.internal.example/v1"
export TRUSSIUM_PROVIDER__API_KEY="gateway-api-key"
uv run python -m trussium
```

Current validation covers text-only, stateless JSON and streaming requests.
It does not cover Ollama's native `/api` endpoints, automatic model discovery,
tools, vision, embeddings, or stateful Responses API conversations.

---

# Running Tests

Execute the complete unit and integration test suite.

```bash
uv run pytest
```

Run only the fast unit suite.

```bash
uv run pytest tests/unit/
```

Run the end-to-end integration suite.

```bash
uv run pytest tests/integration/ -m "not ollama"
```

The integration suite starts the production `python -m trussium` entry point and a deterministic local OpenAI Responses API on dynamically allocated loopback ports. It sends real HTTP requests through Uvicorn and the OpenAI SDK, captures structured runtime logs, and cleans up every child process after the test session.

Integration tests do not require Docker, internet access, an OpenAI account, or real credentials. They never contact the public OpenAI service.

Run the opt-in live Ollama compatibility suite against an already-installed
model:

```bash
TRUSSIUM_OLLAMA_TEST_MODEL="llama3.1:8b" \
  uv run pytest tests/integration/test_ollama_live.py
```

The suite uses `http://127.0.0.1:11434/v1` by default. Override it with
`TRUSSIUM_OLLAMA_TEST_BASE_URL` when validating a remote compatible endpoint.
It skips with a clear reason when the requested server or model is unavailable.

Run a specific test module or test case by passing its path.

```bash
uv run pytest tests/integration/test_chat_runtime.py
```

## Package validation

Build the wheel and source distribution, inspect their metadata and contents,
install each into a clean Python 3.12 environment, and exercise both installed
runtimes:

```bash
scripts/package-smoke-test.sh
```

The default workflow uses a temporary directory. Pass an absolute output path
to keep the validated artifacts:

```bash
mkdir -p dist
scripts/package-smoke-test.sh "$(pwd)/dist"
```

The smoke test verifies isolated production dependencies, distribution and
runtime version alignment, the typing marker, site-packages imports, liveness,
readiness, request correlation, and bounded `SIGTERM` shutdown.

See the [Python Packaging Guide](PACKAGING.md) for the complete artifact
contract, local installation, CI behavior, and GitHub release publication.

## Container validation

Docker is required only for container work. Run Dockerfile build checks and the
complete production-image smoke test:

```bash
docker build --check .
scripts/container-smoke-test.sh
```

The smoke test builds the image, validates its metadata and contents, and runs
it with a read-only filesystem, dropped capabilities, no privilege escalation,
and a dynamic host port. It verifies Docker health, HTTP health endpoints,
request correlation, the non-root runtime identity, and graceful shutdown.

See the [Container Guide](CONTAINERS.md) for build metadata, GHCR tags,
provider configuration, supported platforms, and hardened run commands.

---

# Linting

Run Ruff.

```bash
uv run ruff check .
```

Automatically fix supported issues.

```bash
uv run ruff check . --fix
```

---

# Formatting

Format the project.

```bash
uv run ruff format .
```

---

# Type Checking

Run MyPy.

```bash
uv run mypy src
```

---

# Project Structure

```text
src/
├── trussium/
│   ├── runtime/
│   ├── providers/
│   ├── capabilities/
│   ├── protocols/
│   ├── config/
│   ├── logging/
│   └── ...
│
tests/
│
docs/
│
.github/
```

The project follows the `src` layout to improve packaging consistency and prevent accidental imports from the repository root.

---

# Branch Strategy

The default branch is:

```
main
```

Feature work should be developed on feature branches.

Examples:

```text
feature/provider-registry

feature/openai-provider

fix/runtime-shutdown

docs/update-roadmap
```

---

# Commit Messages

Trussium follows the Conventional Commits specification.

Examples:

```text
feat(runtime): add provider registry

fix(logging): correct JSON formatter

docs: update architecture guide

test(provider): improve coverage

refactor(config): simplify loader

ci: automate releases
```

---

# Pull Requests

Before opening a pull request:

- Ensure all tests pass.
- Ensure Ruff reports no issues.
- Ensure formatting has been applied.
- Update documentation if required.
- Keep pull requests focused on a single logical change.

---

# Versioning

Trussium follows Semantic Versioning.

Releases are generated automatically through GitHub Actions.

Version numbers are determined from Conventional Commit messages.

---

# Architecture Decisions

Significant architectural changes should be discussed before implementation.

Major architectural decisions are documented as Architecture Decision Records (ADRs).

---

# Getting Help

If you have questions about development, architecture, or contributing, please open a GitHub Discussion or Issue.

We welcome feedback and contributions from the community.
