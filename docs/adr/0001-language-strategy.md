# ADR-0001: Language Strategy

**Status:** Accepted

**Date:** 2026-07-23

---

# Context

Trussium is a cloud-native runtime platform composed of multiple components with different operational characteristics.

The project is intended to evolve into an ecosystem consisting of a runtime, command-line interface (CLI), Kubernetes operator, software development kits (SDKs), documentation, and deployment tooling.

No single programming language is equally well suited for every component.

Choosing a single language for the entire ecosystem would simplify development initially but would require compromises in developer experience, performance, ecosystem integration, or operational efficiency.

A language strategy is therefore required to select the most appropriate language for each component while maintaining a cohesive platform.

---

# Decision

Trussium adopts a multi-language architecture.

Each component is implemented using the language that best fits its operational responsibilities.

| Component | Language |
|-----------|----------|
| Runtime | Python |
| CLI | Go |
| Kubernetes Operator | Go |
| Python SDK | Python |
| Go SDK | Go |
| TypeScript SDK | TypeScript |

This strategy optimizes each component independently while maintaining stable interfaces between them.

---

# Rationale

## Runtime

The runtime is responsible for orchestrating requests between applications, AI providers, and future runtime capabilities.

Python provides several advantages:

- Excellent AI and machine learning ecosystem
- First-class support from AI providers
- Mature asynchronous programming
- Rapid development
- Strong ecosystem for API frameworks
- Excellent developer adoption

The runtime is primarily I/O bound rather than CPU bound, making Python an appropriate choice.

Performance-critical workloads remain delegated to external AI providers or specialized inference engines.

---

## CLI

The CLI is implemented in Go.

Reasons include:

- Single statically linked binaries
- Cross-platform compilation
- Fast startup time
- Minimal runtime dependencies
- Excellent developer experience for command-line tooling

The CLI should be easily distributable without requiring users to install Python.

---

## Kubernetes Operator

The Kubernetes Operator is implemented in Go.

Reasons include:

- Native Kubernetes ecosystem
- Official Operator SDK support
- controller-runtime library
- Strong typing
- Efficient concurrency
- Industry standard for Kubernetes controllers

Using Go aligns Trussium with Kubernetes best practices.

---

## SDKs

SDKs are implemented using their native languages.

Examples include:

- Python SDK
- Go SDK
- TypeScript SDK

Each SDK should feel natural for developers within its respective ecosystem.

SDKs expose consistent runtime APIs while following language-specific conventions.

---

# Consequences

## Positive

- Each component uses the most appropriate language.
- Better developer experience across ecosystems.
- Native integration with Kubernetes tooling.
- Native SDK experience for developers.
- Simplified CLI distribution.
- Strong alignment with cloud-native best practices.

## Negative

- Multiple programming languages increase maintenance complexity.
- Contributors may need familiarity with more than one language.
- CI pipelines become more sophisticated.
- Shared design standards become increasingly important.

These trade-offs are considered acceptable given the long-term goals of the project.

---

# Alternatives Considered

## Option 1 — Python Everywhere

Advantages

- Single language.
- Simpler contributor onboarding.
- Shared tooling.

Rejected because:

- CLI distribution is less convenient.
- Kubernetes ecosystem is Go-centric.
- Operator development is less mature.

---

## Option 2 — Go Everywhere

Advantages

- Excellent performance.
- Strong Kubernetes ecosystem.
- Simple deployment.

Rejected because:

- AI provider ecosystems overwhelmingly prioritize Python.
- Reduced access to AI libraries.
- Slower iteration for AI runtime development.

---

## Option 3 — Rust Everywhere

Advantages

- High performance.
- Memory safety.
- Modern tooling.

Rejected because:

- Smaller AI ecosystem.
- Higher contributor barrier.
- Longer development cycles.
- Reduced adoption among AI engineers.

---

# Compliance

Future components should follow this language strategy unless a documented Architecture Decision Record supersedes this decision.

Any deviation should be justified through a new ADR.
