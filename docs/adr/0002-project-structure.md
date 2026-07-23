# ADR-0002: Repository Strategy

**Status:** Accepted

**Date:** 2026-07-23

**Related Documents:**
- ARCHITECTURE.md
- ROADMAP.md

**Supersedes:** None

---

# Context

Trussium is intended to evolve into a cloud-native platform consisting of multiple independently developed components.

These components include the runtime, command-line interface (CLI), Kubernetes operator, language-specific SDKs, documentation, deployment assets, and example applications.

As the ecosystem grows, contributors should be able to work on individual components without introducing unnecessary coupling between unrelated projects.

A repository strategy is therefore required to define how the Trussium ecosystem is organized and maintained.

---

# Decision

Trussium adopts a multi-repository strategy.

Each major component is maintained in its own repository with independent development, release, and versioning lifecycles.

Initial repositories include:

| Repository | Responsibility |
|------------|----------------|
| trussium-runtime | Core runtime platform |
| trussium-cli | Command-line interface |
| trussium-operator | Kubernetes Operator |
| trussium-sdk-python | Python SDK |
| trussium-sdk-go | Go SDK |
| trussium-sdk-typescript | TypeScript SDK |
| trussium-examples | Example applications |
| trussium-docs | Documentation site |
| trussium-helm | Helm charts |

Each repository owns its own codebase, issue tracking, release cadence, and semantic versioning.

---

# Rationale

The Trussium ecosystem contains components with different responsibilities, programming languages, contributor groups, and release frequencies.

Separating these components into dedicated repositories provides several advantages:

- Independent release cycles
- Clear ownership boundaries
- Smaller repositories
- Reduced build complexity
- Simpler dependency management
- Language-specific tooling
- Easier onboarding for contributors

This approach aligns with the modular nature of the Trussium architecture.

---

# Versioning

Each repository follows Semantic Versioning independently.

For example:

| Repository | Version |
|------------|---------|
| trussium-runtime | v1.2.0 |
| trussium-cli | v0.7.0 |
| trussium-sdk-python | v1.1.3 |

Repositories are not required to share identical version numbers.

Version numbers reflect the maturity and release cadence of each individual component.

---

# Release Strategy

Each repository is responsible for its own release process.

Releases are expected to use:

- Semantic Versioning
- Conventional Commits
- Automated GitHub Actions
- Automated Git tags
- Automated GitHub Releases
- Generated changelogs

Release automation should be consistent across all Trussium repositories where practical.

---

# Consequences

## Positive

- Components evolve independently.
- Cleaner separation of concerns.
- Faster CI/CD pipelines.
- Easier contributor onboarding.
- Smaller pull requests.
- Independent release schedules.
- Better language-specific tooling.

## Negative

- Cross-repository changes require coordination.
- More repositories to maintain.
- Shared standards must be documented consistently.
- Version compatibility between repositories must be managed carefully.

These trade-offs are considered acceptable for a long-lived cloud-native platform.

---

# Alternatives Considered

## Option 1 — Monorepo

Advantages

- Single repository.
- Easier cross-component refactoring.
- Simplified dependency updates.
- Unified issue tracking.

Rejected because:

- Increased repository size.
- Slower CI/CD pipelines.
- Multiple languages increase tooling complexity.
- Contributors download unrelated code.
- Independent release cycles become more difficult.

---

## Option 2 — Hybrid Repository Structure

Advantages

- Shared repositories for closely related projects.
- Fewer repositories overall.

Rejected because:

- Repository boundaries become unclear over time.
- Components may become tightly coupled.
- Ownership becomes less obvious.

---

## Option 3 — Multi-Repository

Advantages

- Strong separation of concerns.
- Independent releases.
- Modular ecosystem.
- Clear ownership boundaries.
- Language-specific tooling.
- Better scalability.

Accepted as the long-term repository strategy for Trussium.

---

# Compliance

New repositories should only be created when they represent a distinct architectural component with an independent lifecycle.

Repositories should not be split solely for organizational convenience.

Any significant changes to the repository strategy must be documented through a new Architecture Decision Record.
