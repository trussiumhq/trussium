# Trussium CLI

The installed `trussium` command operates the core runtime. It does not manage
Kubernetes resources or the separate Trussium operator.

Use `trussium --help` to inspect the command surface. The global `--version`
option and the `version` command both print the installed runtime version.

```text
trussium serve
trussium config validate
trussium health --url http://127.0.0.1:9000
trussium capabilities --url http://127.0.0.1:9000
trussium diagnostics --url http://127.0.0.1:9000
trussium diagnostics --url http://127.0.0.1:9000 --provider openai
trussium diagnostics --url http://127.0.0.1:9000 --format text
trussium version
```

`serve` uses the existing runtime settings and server lifecycle. `config
validate` exits with code 2 for invalid settings. `health` checks `/health/ready`
and exits with code 1 when the runtime is unavailable. `version` prints the
installed package version. `capabilities` prints the runtime's public
capability metadata as stable, sorted JSON and exits with code 1 when the
runtime is unavailable or returns invalid JSON. These commands are read-only;
the CLI does not install or manage the runtime, Helm chart, or operator.

`diagnostics` collects bounded readiness, component health, provider health, and
capability availability reports. It prints one stable JSON object and exits
with code 1 if any report cannot be retrieved. It does not expose credentials
or provider payloads. Use `--provider NAME` to limit the provider section to a
single registered provider; all other health sections remain unchanged. Use
`--format text` for a concise human-readable status summary; JSON remains the
default for scripts.
