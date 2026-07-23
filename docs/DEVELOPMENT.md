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

> **Note**
>
> This command may change as the runtime evolves.

---

# Running Tests

Execute the test suite.

```bash
uv run pytest
```

Run a specific test.

```bash
uv run pytest tests/unit/
```

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
