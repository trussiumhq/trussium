# Trussium 1.0.0 Release Candidate

> **Historical manifest — superseded.** The version table below reflects the
> original 1.0.0 proposal and must not be used to tag or publish releases.
> Repository versions have since advanced; use a newly approved candidate
> manifest before beginning major-release publication. The current review
> proposal is [`RELEASE_1_17_CANDIDATE.md`](RELEASE_1_17_CANDIDATE.md).

This historical manifest was a review artifact for change-management issue
[#307](https://github.com/trussiumhq/trussium/issues/307). It does not create
tags or publish releases.

## Proposed release set

| Repository | Current | Candidate | Compatibility target |
| --- | --- | --- | --- |
| `trussium` runtime | `v0.98.1` | `v1.0.0` | `/v1` API and production container |
| `trussium-helm` | `v0.10.0` | `v1.0.0` | Runtime `v1.0.0` |
| `trussium-operator` | `v0.13.2` | `v1.0.0` | Runtime and chart `v1.0.0` |

SDKs and provider adapters remain independently versioned and are not release
prerequisites.

## Approval gates

- [ ] Breaking-change and stability contract reviewed.
- [ ] Runtime, chart, and operator release notes approved.
- [ ] Candidate versions and compatibility metadata updated in release PRs.
- [ ] Full CI, package, container, Helm, and operator validation passes.
- [ ] Rollback and artifact recovery procedures reviewed.
- [ ] Explicit approval recorded in issue #307 before tagging or publication.

## Publication order

1. Publish runtime `v1.0.0` and verify its package/container artifacts.
2. Update and publish Helm chart `v1.0.0` against the verified runtime.
3. Update and publish operator `v1.0.0` against the verified runtime/chart pair.
4. Verify release assets, OCI artifacts, package metadata, and compatibility
   documentation in each repository.
