# Model Context Protocol

Trussium exposes an optional, bounded MCP JSON-RPC surface for explicitly
registered tools. It is disabled by default and every call delegates to the
same `ToolExecutor` used by the REST API.

## Enablement

Applications embedding Trussium can enable the surface with
`create_application(..., mcp_enabled=True)`. The endpoint is:

```text
POST /v1/mcp
```

When disabled, the endpoint returns `404` with `mcp_unavailable`. When enabled
without an application-owned tool executor, it returns `503` with
`tools_unavailable`.

## Supported methods

- `ping` returns an empty success result for bounded liveness handshakes.
- `notifications/initialized` is accepted as a notification after client
  initialization and returns no JSON-RPC body.
- `initialize` returns the supported protocol version and tool capability.
- `tools/list` returns safe names, descriptions, and the declared Pydantic JSON
  input schema for registered tools. Clients can validate arguments before
  invoking a tool. For larger registries, pass the returned opaque `nextCursor`
  as `params.cursor`; responses are capped at 50 tools per page.
- `tools/call` executes one registered tool with bounded validation and
  runtime-owned deadlines.

The first slice intentionally excludes subscriptions, prompts, resources,
remote discovery, and transport upgrades. REST and SSE APIs remain the primary
runtime integration surfaces.

## Status codes and errors

Enabled JSON-RPC requests return HTTP `200`, including JSON-RPC error objects.
The lifecycle notification `notifications/initialized` returns HTTP `202` with
an empty body. HTTP `404` (`mcp_unavailable`) means MCP is disabled, while
HTTP `503` (`tools_unavailable`) means no application-owned tool executor is
registered. Malformed request bodies are rejected by the HTTP validation layer
with `422`.

JSON-RPC error codes are stable and intentionally bounded:

| Code | Meaning |
| --- | --- |
| `-32601` | Method not supported |
| `-32602` | Invalid method parameters or cursor |
| `-32004` | Tool not found |
| `-32003` | Tool authorization denied |
| `-32002` | Tool approval timed out |
| `-32001` | Tool execution timed out |
| `-32000` | Tool execution failed |

## Safety and compatibility

Tool authorization, optional approval, cancellation, lifecycle events, audit
records, and error normalization remain owned by `ToolExecutor`. MCP responses
do not expose credentials, provider payloads, or raw handler exception text.
Existing REST and SSE contracts are unchanged.
