# Go SDK

The Go SDK is maintained in the dedicated
[`trussium-go`](https://github.com/trussiumhq/trussium-go) repository and
published as the `github.com/trussiumhq/trussium-go` module. It calls an
existing local, private, or public runtime; it does not install, host, or
configure one.

```bash
go get github.com/trussiumhq/trussium-go
```

See the dedicated repository for context-aware chat, readiness, capability
discovery, request correlation, and typed runtime API errors.

For a runnable self-hosted workflow, see the dedicated repository's
[`examples/basic/main.go`](https://github.com/trussiumhq/trussium-go/blob/main/examples/basic/main.go).
It accepts `TRUSSIUM_URL`, `TRUSSIUM_MODEL`, and `TRUSSIUM_PROMPT` and checks
readiness and capabilities before making a completion request:

```bash
TRUSSIUM_URL=http://127.0.0.1:9000 \
TRUSSIUM_MODEL=llama3.1:8b \
TRUSSIUM_PROMPT="Say hello." \
go run ./examples/basic
```
