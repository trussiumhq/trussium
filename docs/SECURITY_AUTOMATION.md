# Security automation

The public repository runs CodeQL for Python, audits the locked Python dependency set with `pip-audit`, and scans repository history and pull requests for committed secrets with Gitleaks. These checks run on pull requests, pushes to `main`, and weekly schedules where supported.

The scans are repository hygiene controls. Provider credentials must still be injected through deployment secret mechanisms, and operators should rotate any credential that may have been exposed. Release recovery steps are documented in the release workflow and should be followed without rebuilding an already-tagged artifact.
