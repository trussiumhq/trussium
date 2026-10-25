# Security automation

This repository has automated source-level security checks:

- CodeQL analyzes Python on pull requests, pushes to `main`, and a weekly schedule.
- The dependency workflow exports the locked runtime and development groups from `uv.lock` and audits them with `pip-audit` on pull requests, pushes to `main`, and a weekly schedule.
- Gitleaks scans repository history on pull requests, pushes to `main`, and a weekly schedule.
- Dependabot checks the configured `pip`, GitHub Actions, and Docker ecosystems weekly.

These workflow and configuration files describe this repository's automation; they do not prove the state of repository-level GitHub security settings. In particular, the Gitleaks workflow is not a substitute for GitHub's native secret-scanning alerts or push protection. Those settings, along with Dependabot vulnerability alerts and repository-level code-scanning status, must be verified in GitHub's Security settings for each repository. The cross-repository inventory and remaining gaps are tracked in [issue #465](https://github.com/trussiumhq/trussium/issues/465).

## Public repository file-level inventory

This inventory was checked against workflow and manifest files on each
repository's GitHub default branch on 2026-10-22. It records visible automation,
not successful scan runs or GitHub-side security settings. “Not found” means no
matching workflow was found at the standard paths inspected; it is not proof
that no organization-level or GitHub-default analysis exists.

| Public repository | Primary project content | CI workflow | Dependency scanning in repository files | CodeQL evidence |
| --- | --- | --- | --- | --- |
| [trussium](https://github.com/trussiumhq/trussium) | Python runtime | Yes | `pip-audit`, Gitleaks; Dependabot: pip, Actions, Docker | Workflow present |
| [trussium-python](https://github.com/trussiumhq/trussium-python) | Python SDK | Yes | `pip-audit`; Dependabot: uv | Workflow present |
| [trussium-go](https://github.com/trussiumhq/trussium-go) | Go SDK | Yes | `govulncheck`; Dependabot: Go modules | Workflow present |
| [trussium-operator](https://github.com/trussiumhq/trussium-operator) | Go / Kubernetes Operator | Yes | Dependabot: Go modules, Actions, Docker; no dedicated audit workflow found | Workflow present |
| [trussium-knowledge-agent](https://github.com/trussiumhq/trussium-knowledge-agent) | Python | Yes | `pip-audit`; Dependabot: pip, Actions | Workflow present |
| [trussiumctl](https://github.com/trussiumhq/trussiumctl) | Go CLI | Yes | `govulncheck`; Dependabot: Go modules, Actions | Analysis was reported in issue #465; workflow not found at inspected paths |
| [trussium-typescript](https://github.com/trussiumhq/trussium-typescript) | TypeScript SDK | Yes | Dependabot: npm, Actions; no dedicated audit workflow found | Workflow not found |
| [trussium-provider-vllm](https://github.com/trussiumhq/trussium-provider-vllm) | Python provider | Yes | Dependabot: pip, Actions; no dedicated audit workflow found | Workflow not found |
| [trussium-provider-anthropic](https://github.com/trussiumhq/trussium-provider-anthropic) | Python provider | Yes | Dependabot: pip, Actions; no dedicated audit workflow found | Workflow not found |
| [trussium-provider-libretranslate](https://github.com/trussiumhq/trussium-provider-libretranslate) | Python provider | Yes | Dependabot: pip, Actions; no dedicated audit workflow found | Workflow not found |
| [trussium-provider-piper](https://github.com/trussiumhq/trussium-provider-piper) | Python provider | Yes | Dependabot: pip, Actions; no dedicated audit workflow found | Workflow not found |
| [trussium-helm](https://github.com/trussiumhq/trussium-helm) | Helm chart / YAML and tooling | Yes | Dependabot: pip, Actions; no dedicated audit workflow found | Not identified as a primary code target; confirm repository language/settings |
| [trussiumhq.github.io](https://github.com/trussiumhq/trussiumhq.github.io) | MkDocs documentation site | Pages build/deploy | Dependabot: pip, Actions | Not applicable to documentation content |

On 2026-10-25, GitHub's organization security configuration was assigned to all 13 public repositories, excluding the two private cloud repositories. It enables secret-scanning alerts and push protection, does not enforce repository-owner settings, and leaves CodeQL, dependency-graph, and Dependabot settings unchanged. The initial rollout had six CodeQL advanced-setup conflicts; after narrowing the policy and retrying, all 13 public repositories were assigned with no failures. Assignment is not proof of effective per-repository settings because repository owners may override it; verify effective settings before treating coverage as closed. Do not treat Gitleaks CI coverage as evidence that GitHub alerts or push protection are enabled. Provider credentials must be injected through deployment secret mechanisms. Rotate any credential that may have been exposed. For release recovery, follow the release workflow and do not rebuild an already-tagged artifact.
