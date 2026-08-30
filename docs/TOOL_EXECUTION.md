# Controlled tool execution

Trussium can execute only tools explicitly registered by the application. The
runtime does not discover functions or interpret inputs as shell commands,
filesystem paths, URLs, or code.

`POST /v1/tools/executions` accepts a tool name and JSON-object arguments. A
tool executor must be supplied during application composition; otherwise the
endpoint returns `503 tools_unavailable`.

## Registering a tool

Applications define the input contract and explicitly compose the allowlist:

```python
from pydantic import BaseModel, ConfigDict

from trussium.app import create_application
from trussium.tools import RegisteredTool, ToolExecutor, ToolRegistry


class EchoArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value: str


async def echo(arguments: BaseModel) -> dict[str, object]:
    return {"value": arguments.model_dump()["value"]}


app = create_application(
    tool_executor=ToolExecutor(ToolRegistry((RegisteredTool("echo", EchoArguments, echo),)))
)
```

The client can then send `{"name": "echo", "arguments": {"value": "hello"}}`.

Each execution is allowlisted, validated against the registered tool's Pydantic
argument model, and bounded by a default ten-second deadline. Tool arguments,
results, credentials, and exception messages are excluded from structured logs.
Safe audit events contain only the registered tool name, stable outcome, and
the request and execution context already attached by the runtime.

Remote tools, approval workflows, dynamic plugins, and agent-directed selection
are separate future work.
