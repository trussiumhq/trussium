# Trussium CLI

The installed `trussium` command operates the core runtime. It does not manage
Kubernetes resources or the separate Trussium operator.

```text
trussium serve
trussium config validate
trussium health --url http://127.0.0.1:9000
trussium version
```

`serve` uses the existing runtime settings and server lifecycle. `config
validate` exits with code 2 for invalid settings. `health` checks `/health/ready`
and exits with code 1 when the runtime is unavailable. `version` prints the
installed package version.
