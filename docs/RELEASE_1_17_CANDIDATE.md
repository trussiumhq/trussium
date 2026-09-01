# Trussium 1.17.0 Release Candidate

> **Review artifact — no tags or publication.** This manifest proposes a
> coordinated minor-release baseline for explicit review and approval.

This candidate is tracked by issue
[#393](https://github.com/trussiumhq/trussium/issues/393). It does not create
tags, publish packages, or authorize a release.

## Proposed release set

| Repository | Current | Candidate | Compatibility target |
| --- | --- | --- | --- |
| `trussium` runtime | `v1.16.0` | `v1.17.0` | `/v1` API and bounded Agent Runtime slice |
| `trussium-helm` | `v1.0.0` | `v1.1.0` | Runtime `v1.17.0` |
| `trussium-operator` | `v1.0.0` | `v1.1.0` | Runtime and chart `v1.1.0` |

SDKs and provider adapters remain independently versioned and optional. They
are not prerequisites for this coordinated runtime, chart, and operator
release.

The runtime candidate includes the bounded Agent Runtime slice: workflow
execution, tool execution, policy and approval contracts, audit delivery,
observability, and the security boundary. Durable persistence, replay,
distributed orchestration, and hosted authorization remain separately deferred
and are not implied by this candidate.

## Approval gates

- [ ] Breaking-change and stability contracts reviewed.
- [ ] Runtime, chart, and operator release notes approved.
- [ ] Candidate versions and compatibility metadata updated in release PRs.
- [ ] Full CI, package, container, Helm, and operator validation passes.
- [ ] Rollback and artifact recovery procedures reviewed.
- [ ] Explicit approval recorded in issue #393 before tagging or publication.

## Publication order after approval

1. Publish runtime `v1.17.0` and verify package and container artifacts.
2. Update and publish Helm chart `v1.1.0` against the verified runtime.
3. Update and publish operator `v1.1.0` against the verified runtime/chart pair.
4. Verify release assets, OCI artifacts, package metadata, and compatibility
   documentation in each repository.
