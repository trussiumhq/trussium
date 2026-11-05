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

The four `undici` alerts recorded on 2026-10-29 were fixed by TypeScript SDK
[PR #29](https://github.com/trussiumhq/trussium-typescript/pull/29), merged on
2026-11-05. The lockfile now resolves the bundled npm dependency to 11.21.2,
which contains `undici` 6.29.1. GitHub now reports the four corresponding
alerts (#20, #22, #23, and #24) as fixed; the SDK's Node 20 and Node 22 checks
passed.

The fixed alerts followed the transitive release-tool path
`semantic-release` → `@semantic-release/npm` → bundled npm → `undici` 6.29.0.
Three were high severity and one was moderate:

- High: [GHSA-xjj6-f33q-929c](https://github.com/advisories/GHSA-xjj6-f33q-929c),
  denial of service via excessive content encodings (Dependabot alert #20).
- Moderate: [GHSA-9fm3-97px-rjf6](https://github.com/advisories/GHSA-9fm3-97px-rjf6),
  denial of service via unbounded WebSocket PONG buffering (alert #22).
- High: [GHSA-qrxm-fqhp-jwvm](https://github.com/advisories/GHSA-qrxm-fqhp-jwvm),
  denial of service via TLS 1.2 certificate-changing renegotiation (alert #23).
- High: [GHSA-2m5v-pch6-74hx](https://github.com/advisories/GHSA-2m5v-pch6-74hx),
  TLS certificate validation bypass when Agent TLS options are dropped (alert #24).

The four advisories identified `undici` 6.29.1 as the earliest patched release.
npm CLI [PR #10170](https://github.com/npm/cli/pull/10170) added that update,
and stable npm 11.21.2 was subsequently published with the fix. Updating the
supported npm bundle was the validated remediation.

One moderate alert remains open in the TypeScript SDK:
[GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249),
Dependabot alert [#26](https://github.com/trussiumhq/trussium-typescript/security/dependabot/26).
The lockfile resolves bundled `minimatch` 10.2.5 under npm 11.21.2; GitHub
identifies 11.0.1 as the first patched version. The post-merge Dependabot
security-update job [#42106985380](https://github.com/trussiumhq/trussium-typescript/actions/runs/42106985380)
has not produced a fix. Its updater reported that the available update path
still resolves `minimatch` to 9.0.3, while the current lockfile records the
bundled copy as 10.2.5; treat this as an unresolved upstream/tooling path, not
as a closed alert.

There is a version-range discrepancy between the sources: GitHub's advisory
database and Dependabot report `>=7.0.0, <11.0.1`, while the
[upstream maintainer advisory](https://github.com/isaacs/minimatch/security/advisories/GHSA-g3hv-75wg-m249)
identifies 10.2.6 as affected. The checked-in bundled version is 10.2.5, not
the version specifically named by the upstream advisory. Until the advisory
scope is clarified, keep alert #26 open and describe 10.2.5 as flagged by
GitHub, not as confirmed affected by the upstream report. Do not force an
override into npm's bundled dependency tree or dismiss the alert as inaccurate.

The SDK's `npm audit` currently reports 35 moderate findings in the
development-only release-tool dependency tree, including the remaining
`minimatch` finding; the lock-only undici fix did not make the full audit clean.
Keep alert #26 open, avoid forcing an incompatible npm major or dismissing the
finding, and rerun the SDK tests, `npm audit`, and GitHub alert check when a
supported bundle with patched `minimatch` is available.

Sources: the four [undici advisories](https://github.com/advisories/GHSA-xjj6-f33q-929c),
[GHSA-9fm3-97px-rjf6](https://github.com/advisories/GHSA-9fm3-97px-rjf6),
[GHSA-qrxm-fqhp-jwvm](https://github.com/advisories/GHSA-qrxm-fqhp-jwvm),
[GHSA-2m5v-pch6-74hx](https://github.com/advisories/GHSA-2m5v-pch6-74hx),
[minimatch GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249)
and the [upstream minimatch advisory](https://github.com/isaacs/minimatch/security/advisories/GHSA-g3hv-75wg-m249),
[npm CLI PR #10170](https://github.com/npm/cli/pull/10170), and
[npm CLI releases](https://github.com/npm/cli/releases).

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
