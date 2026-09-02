"""Optional bounded Model Context Protocol JSON-RPC surface."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from trussium.tools import (
    ToolApprovalTimeoutError,
    ToolAuthorizationError,
    ToolExecutor,
    ToolInvocation,
    ToolNotFoundError,
)

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
    """Handle the bounded MCP handshake and tool methods."""
    executor = _executor(request)
    if message.method == "ping":
        return {"jsonrpc": "2.0", "id": message.id, "result": {}}
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
                        "inputSchema": executor.registry.require(
                            tool.name
                        ).arguments_model.model_json_schema(),
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
        except ToolNotFoundError:
            return {
                "jsonrpc": "2.0",
                "id": message.id,
                "error": {"code": -32004, "message": "Tool not found."},
            }
        except ToolAuthorizationError:
            return {
                "jsonrpc": "2.0",
                "id": message.id,
                "error": {"code": -32003, "message": "Tool authorization denied."},
            }
        except ToolApprovalTimeoutError:
            return {
                "jsonrpc": "2.0",
                "id": message.id,
                "error": {"code": -32002, "message": "Tool approval timed out."},
            }
        except TimeoutError:
            return {
                "jsonrpc": "2.0",
                "id": message.id,
                "error": {"code": -32001, "message": "Tool execution timed out."},
            }
        except Exception:
            return {
                "jsonrpc": "2.0",
                "id": message.id,
                "error": {"code": -32000, "message": "Tool execution failed."},
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
