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
  runtime-owned deadlines. Successful results include `isError: false` and
  preserve the tool output in the `content` array.

The first slice intentionally excludes subscriptions, prompts, resources,
remote discovery, and transport upgrades. REST and SSE APIs remain the primary
runtime integration surfaces.

## Calling a fixed remote MCP tool

Applications that embed Trussium can explicitly register a fixed remote MCP
tool using `RemoteMCPTool`. The URL, remote name, argument model, and bearer
token are application configuration; workflow requests can select only the
local registered name. The adapter does not call `tools/list` or perform
request-time discovery.

```python
import os

from pydantic import BaseModel, ConfigDict

from trussium.app import create_application
from trussium.tools import RemoteMCPTool, ToolExecutor, ToolRegistry


class SearchArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    query: str


remote_search = RemoteMCPTool(
    name="knowledge.search",
    endpoint_url="https://knowledge-agent.example/v1/mcp",
    remote_name="docs.search",
    arguments_model=SearchArguments,
    bearer_token=os.environ["KNOWLEDGE_AGENT_TOOL_TOKEN"],
).registered_tool()

app = create_application(
    tool_executor=ToolExecutor(ToolRegistry((remote_search,))),
    mcp_enabled=True,
)
```

This is an application-composition API, not a setting for the packaged
`trussium` command. The default command remains tool-free. The remote endpoint
must use HTTPS and the exact `/v1/mcp` path. Explicit local development may use
loopback HTTP only with `allow_local_http=True`. Redirects and ambient proxy
settings are disabled. Each call is bounded by the configured remote timeout,
the enclosing `ToolExecutor` deadline, and a 1 MiB request/response limit.
Only request and execution correlation IDs are forwarded; arbitrary inbound
headers, arguments, credentials, and provider payloads are not logged.

The application must still protect the remote MCP endpoint with authentication
and expose only its read-only allowlisted operations. The Knowledge Agent is an
example integration with fixed `docs.search` and `docs.audit_links` operations.
See the [published workflow guide](https://trussiumhq.github.io/agent-workflows/)
for configuration and SDK examples, and the accepted
[cross-process tool boundary ADR](adr/0045-cross-process-agent-tool-boundary.md)
for the security decision.

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
