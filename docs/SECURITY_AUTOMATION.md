# Security automation

This repository has automated source-level security checks:

- CodeQL analyzes Python on pull requests, pushes to `main`, and a weekly schedule.
- The dependency workflow exports the locked runtime and development groups from `uv.lock` and audits them with `pip-audit` on pull requests, pushes to `main`, and a weekly schedule.
- Gitleaks scans repository history on pull requests, pushes to `main`, and a weekly schedule.
- Dependabot checks the configured `pip`, GitHub Actions, and Docker ecosystems weekly.

These workflow and configuration files describe this repository's automation; they do not prove the state of repository-level GitHub security settings. In particular, the Gitleaks workflow is not a substitute for GitHub's native secret-scanning alerts or push protection. Those settings, along with Dependabot vulnerability alerts and repository-level code-scanning status, must be verified in GitHub's Security settings for each repository. The cross-repository inventory and remaining gaps are tracked in [issue #465](https://github.com/trussiumhq/trussium/issues/465).

## Public repository file-level inventory

This inventory was checked against workflow and manifest files on each
repository's GitHub default branch on 2026-10-22. CodeQL status for the
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
| [trussium-operator](https://github.com/trussiumhq/trussium-operator) | Go / Kubernetes Operator | Yes | Dependabot: Go modules, Actions, Docker; no dedicated audit workflow found | Workflow present |
| [trussium-knowledge-agent](https://github.com/trussiumhq/trussium-knowledge-agent) | Python | Yes | `pip-audit`; Dependabot: pip, Actions | Workflow present |
| [trussiumctl](https://github.com/trussiumhq/trussiumctl) | Go CLI | Yes | `govulncheck`; Dependabot: Go modules, Actions | Advanced setup enabled; last scan observed 2026-10-19 |
| [trussium-typescript](https://github.com/trussiumhq/trussium-typescript) | TypeScript SDK | Yes | Dependabot: npm, Actions; no dedicated audit workflow found | GitHub default setup enabled; recent scan observed 2026-10-25 |
| [trussium-provider-vllm](https://github.com/trussiumhq/trussium-provider-vllm) | Python provider | Yes | Dependabot: pip, Actions; no dedicated audit workflow found | GitHub default setup enabled; recent scan observed 2026-10-25 |
| [trussium-provider-anthropic](https://github.com/trussiumhq/trussium-provider-anthropic) | Python provider | Yes | Dependabot: pip, Actions; no dedicated audit workflow found | GitHub default setup enabled; recent scan observed 2026-10-25 |
| [trussium-provider-libretranslate](https://github.com/trussiumhq/trussium-provider-libretranslate) | Python provider | Yes | Dependabot: pip, Actions; no dedicated audit workflow found | GitHub default setup enabled; recent scan observed 2026-10-25 |
| [trussium-provider-piper](https://github.com/trussiumhq/trussium-provider-piper) | Python provider | Yes | Dependabot: pip, Actions; no dedicated audit workflow found | GitHub default setup enabled; recent scan observed 2026-10-25 |
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

### TypeScript SDK dependency alert checkpoint

On 2026-10-25, GitHub showed one open Dependabot alert in
`trussium-typescript`: high-severity `undici` GHSA-xjj6-f33q-929c, detected
through `semantic-release` → `@semantic-release/npm` → bundled `npm` 11.21.1.
The alert identifies `undici` 6.29.1 as the first patched release; the npm
11.21.1 bundle currently resolves 6.29.0. Security PRs #23, #24, and #26
updated the directly managed `undici`, Handlebars, and npm bundle lock data,
but this bundled copy remains affected. A scoped npm override was tested
locally and did not replace npm's bundled copy, so it is not a valid fix. Keep
this alert open until the bundled dependency is actually patched or a
supported upstream dependency update removes the vulnerable version. Re-run
the SDK tests, npm audit, and GitHub alert check after remediation.

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
