"""Optional bounded Model Context Protocol JSON-RPC surface."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from trussium.tools import ToolExecutor, ToolInvocation

router = APIRouter(prefix="/v1/mcp", tags=["mcp"])


class MCPRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    jsonrpc: str = Field(pattern="^2\\.0$")
    id: int | str | None = None
    method: str = Field(min_length=1, max_length=64)
    params: dict[str, Any] = Field(default_factory=dict)


def _executor(request: Request) -> ToolExecutor:
    if not getattr(request.app.state, "mcp_enabled", False):
        raise HTTPException(status_code=404, detail={"code": "mcp_unavailable"})
    executor = getattr(request.app.state, "tool_executor", None)
    if not isinstance(executor, ToolExecutor):
        raise HTTPException(status_code=503, detail={"code": "tools_unavailable"})
    return executor


@router.post("")
async def mcp_json_rpc(message: MCPRequest, request: Request) -> dict[str, Any]:
    """Handle initialize, tools/list, and tools/call only."""
    executor = _executor(request)
    if message.method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": message.id,
            "result": {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "trussium", "version": "1"},
            },
        }
    if message.method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": message.id,
            "result": {
                "tools": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": {"type": "object"},
                    }
                    for tool in executor.registry.discover()
                ]
            },
        }
    if message.method == "tools/call":
        name = message.params.get("name")
        arguments = message.params.get("arguments", {})
        if not isinstance(name, str) or not isinstance(arguments, dict):
            return {
                "jsonrpc": "2.0",
                "id": message.id,
                "error": {"code": -32602, "message": "Invalid tools/call parameters."},
            }
        try:
            result = await executor.execute(ToolInvocation(name=name, arguments=arguments))
        except Exception as error:
            return {
                "jsonrpc": "2.0",
                "id": message.id,
                "error": {"code": -32000, "message": type(error).__name__},
            }
        return {
            "jsonrpc": "2.0",
            "id": message.id,
            "result": {"content": [{"type": "json", "json": result.output}]},
        }
    return {
        "jsonrpc": "2.0",
        "id": message.id,
        "error": {"code": -32601, "message": "Method not supported."},
    }
