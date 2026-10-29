# Security automation

This repository has automated source-level security checks:

- CodeQL analyzes Python on pull requests, pushes to `main`, and a weekly schedule.
- The dependency workflow exports the locked runtime and development groups from `uv.lock` and audits them with `pip-audit` on pull requests, pushes to `main`, and a weekly schedule.
- Gitleaks scans repository history on pull requests, pushes to `main`, and a weekly schedule.
- Dependabot checks the configured `pip`, GitHub Actions, and Docker ecosystems weekly.

These workflow and configuration files describe this repository's automation; they do not prove the state of repository-level GitHub security settings. In particular, the Gitleaks workflow is not a substitute for GitHub's native secret-scanning alerts or push protection. Those settings, along with Dependabot vulnerability alerts and repository-level code-scanning status, must be verified in GitHub's Security settings for each repository. The cross-repository inventory and remaining gaps are tracked in [issue #465](https://github.com/trussiumhq/trussium/issues/465).

## Public repository file-level inventory

This inventory was checked against workflow and manifest files on each
repository's GitHub default branch on 2026-10-25. CodeQL status for the
TypeScript SDK, four Python providers, `trussiumctl`, and `trussium-helm` was
separately verified in GitHub's Advanced Security settings on 2026-10-25.
“Not found” means no matching workflow was found at the standard paths
inspected; it is not proof that no GitHub default-setup analysis exists. The
CodeQL column records that distinction where the settings were verified.

| Public repository | Primary project content | CI workflow | Dependency scanning in repository files | CodeQL evidence |
| --- | --- | --- | --- | --- |
| [trussium](https://github.com/trussiumhq/trussium) | Python runtime | Yes | `pip-audit`, Gitleaks; Dependabot: pip, Actions, Docker | Workflow present |
| [trussium-python](https://github.com/trussiumhq/trussium-python) | Python SDK | Yes | `pip-audit`; Dependabot: uv | Workflow present |
| [trussium-go](https://github.com/trussiumhq/trussium-go) | Go SDK | Yes | `govulncheck`; Dependabot: Go modules | Workflow present |
| [trussium-operator](https://github.com/trussiumhq/trussium-operator) | Go / Kubernetes Operator | Yes | `govulncheck`; Dependabot: Go modules, Actions, Docker | Workflow present |
| [trussium-knowledge-agent](https://github.com/trussiumhq/trussium-knowledge-agent) | Python | Yes | `pip-audit`; Dependabot: pip, Actions | Workflow present |
| [trussiumctl](https://github.com/trussiumhq/trussiumctl) | Go CLI | Yes | `govulncheck`; Dependabot: Go modules, Actions | Advanced setup enabled; last scan observed 2026-10-19 |
| [trussium-typescript](https://github.com/trussiumhq/trussium-typescript) | TypeScript SDK | Yes | Dependabot: npm, Actions; no dedicated audit workflow found | GitHub default setup enabled; recent scan observed 2026-10-25 |
| [trussium-provider-vllm](https://github.com/trussiumhq/trussium-provider-vllm) | Python provider | Yes | Locked environment + scheduled/PR `pip-audit`; Dependabot: pip, Actions | GitHub default setup enabled; recent scan observed 2026-10-25 |
| [trussium-provider-anthropic](https://github.com/trussiumhq/trussium-provider-anthropic) | Python provider | Yes | Locked environment + scheduled/PR `pip-audit`; Dependabot: pip, Actions | GitHub default setup enabled; recent scan observed 2026-10-25 |
| [trussium-provider-libretranslate](https://github.com/trussiumhq/trussium-provider-libretranslate) | Python provider | Yes | Locked environment + scheduled/PR `pip-audit`; Dependabot: pip, Actions | GitHub default setup enabled; recent scan observed 2026-10-25 |
| [trussium-provider-piper](https://github.com/trussiumhq/trussium-provider-piper) | Python provider | Yes | Locked environment + scheduled/PR `pip-audit`; Dependabot: pip, Actions | GitHub default setup enabled; recent scan observed 2026-10-25 |
| [trussium-helm](https://github.com/trussiumhq/trussium-helm) | Helm chart / YAML and tooling | Yes | Dependabot: pip, Actions; no dedicated audit workflow found | GitHub default setup enabled; last scan observed 2026-10-25 |
| [trussiumhq.github.io](https://github.com/trussiumhq/trussiumhq.github.io) | MkDocs documentation site | Pages build/deploy | Dependabot: pip, Actions | Not applicable to documentation content |

GitHub default CodeQL setup is enabled for the TypeScript SDK and the four
Python provider repositories listed above, with recent scans observed on
2026-10-25. The `trussiumctl` repository uses advanced setup and had a scan
observed on 2026-10-19; `trussium-helm` uses default setup and had a scan on
2026-10-25. A trial advanced-setup workflow in the TypeScript and provider
repositories failed result upload because GitHub default setup was already
active. Those duplicate workflows were closed without merging. Keep one
CodeQL mode active per repository; do not treat the absence of a workflow file
as a coverage gap when default setup is enabled. This verifies that scans ran,
not that the resulting alerts have all been triaged or fixed.

### Provider dependency remediation

On 2026-10-25, `pip-audit` found GitPython 3.2.0 in the development
environments of all four Python provider repositories. GitPython 3.2.0 is
affected by [GHSA-83vg-56qc-22m7](https://github.com/advisories/GHSA-83vg-56qc-22m7);
3.2.1 is the patched release. The provider constraints were updated to require
3.2.1 or later within the 3.2 series, and committed `uv.lock` files now make
those environments reproducible. The changes were merged in
[vLLM PR #24](https://github.com/trussiumhq/trussium-provider-vllm/pull/24),
[Anthropic PR #22](https://github.com/trussiumhq/trussium-provider-anthropic/pull/22),
[LibreTranslate PR #11](https://github.com/trussiumhq/trussium-provider-libretranslate/pull/11),
and [Piper PR #11](https://github.com/trussiumhq/trussium-provider-piper/pull/11).
Each repository now audits the synced project environment on pull requests,
default-branch pushes, and a weekly schedule. The post-update audits reported
no known vulnerabilities.

`pip-audit` cannot match the Git-installed Trussium runtime or local provider
project package to PyPI advisory records, so it reports and skips those two
package records; it still audits their installed transitive dependencies that
are published to PyPI. Keep Dependabot enabled and review the upstream Trussium
repository for advisories affecting Git-sourced code as well.

The Operator's baseline `govulncheck` scan found reachable advisories in
`golang.org/x/net` 0.58.0 (fixed in 0.60.0), an advisory in
`github.com/google/cel-go` 0.29.2 (fixed in 0.30.0), and standard-library
findings with Go 1.26.4. The fixes and a pinned `govulncheck` workflow are in
[Operator PR #219](https://github.com/trussiumhq/trussium-operator/pull/219).
The PR's full CI and compatibility matrix passed, and its vulnerability check
reported no findings under Go 1.26.10. The default-branch workflow now covers
pull requests, default-branch pushes, weekly scheduled scans, and manual runs.

### TypeScript SDK dependency alert checkpoint

On 2026-10-29, GitHub showed four open Dependabot alerts for `undici` in the
`trussium-typescript` lockfile. All four follow the same transitive release-tool
path: `semantic-release` → `@semantic-release/npm` → bundled `npm` 11.21.1 →
`undici` 6.29.0. Three alerts are high severity and one is moderate:

- High: [GHSA-xjj6-f33q-929c](https://github.com/advisories/GHSA-xjj6-f33q-929c),
  denial of service via excessive content encodings (Dependabot alert #20).
- Moderate: [GHSA-9fm3-97px-rjf6](https://github.com/advisories/GHSA-9fm3-97px-rjf6),
  denial of service via unbounded WebSocket PONG buffering (alert #22).
- High: [GHSA-qrxm-fqhp-jwvm](https://github.com/advisories/GHSA-qrxm-fqhp-jwvm),
  denial of service via TLS 1.2 certificate-changing renegotiation (alert #23).
- High: [GHSA-2m5v-pch6-74hx](https://github.com/advisories/GHSA-2m5v-pch6-74hx),
  TLS certificate validation bypass when Agent TLS options are dropped (alert #24).

Each advisory identifies `undici` 6.29.1 as the earliest patched release; the
bundled copy still resolves to 6.29.0. The npm CLI merged an update to
`undici` 6.29.1 into its `latest` development branch in
[PR #10170](https://github.com/npm/cli/pull/10170) on 2026-10-27. That change
is not yet in a published stable npm package: the npm CLI release page and
registry still identify 12.2.1 as the latest stable release, and the 12.2.2
release PR remains open. Security PRs 23, 24, and 26 updated the directly
managed `undici`, Handlebars, and npm bundle lock data, but this bundled copy
remains affected. A scoped npm override was tested locally and did not replace
npm's bundled copy, so it is not a valid fix. Do not consume an unreleased CLI
branch or adopt a semantic-release prerelease as a production workaround. Keep
all four alerts open until a supported stable bundle contains the patched
dependency, then rerun SDK tests, `npm audit`, and the GitHub alert check.

Sources: the four [undici advisories](https://github.com/advisories/GHSA-xjj6-f33q-929c),
[GHSA-9fm3-97px-rjf6](https://github.com/advisories/GHSA-9fm3-97px-rjf6),
[GHSA-qrxm-fqhp-jwvm](https://github.com/advisories/GHSA-qrxm-fqhp-jwvm), and
[GHSA-2m5v-pch6-74hx](https://github.com/advisories/GHSA-2m5v-pch6-74hx),
[npm CLI PR #10170](https://github.com/npm/cli/pull/10170),
[npm CLI releases](https://github.com/npm/cli/releases), and
[npm registry metadata](https://registry.npmjs.org/npm/latest).
[semantic-release releases](https://github.com/semantic-release/semantic-release/releases).

On 2026-10-25, GitHub's organization security configuration was verified as
assigned to all 13 public repositories, excluding the two private cloud
repositories. It enables secret-scanning alerts and push protection, and does
not enforce repository-owner settings. A separate read-only check of the
Advanced Security settings page for each of the 13 public repositories showed
secret protection, push protection, the dependency graph, Dependabot alerts,
and Dependabot security updates enabled. This direct per-repository check is
the evidence for effective settings; the organization configuration leaves
dependency graph, Dependabot alerts, Dependabot security updates, and CodeQL
default setup unset. Its coverage card reports 0% Dependabot repositories
protected by that configuration, which is distinct from the enabled
repository-level settings. The initial rollout had six CodeQL advanced-setup
conflicts; after narrowing the configuration to the approved secret-scanning
settings and retrying, GitHub showed all 13 public repositories assigned and
no failed repositories. Repository owners may still change settings, so rerun
this check periodically. Do not treat Gitleaks CI coverage as evidence that
GitHub alerts or push protection are enabled. Provider credentials must be
injected through deployment secret mechanisms. Rotate any credential that may
have been exposed.

For release recovery, follow the release workflow and do not rebuild an
already-tagged artifact.
