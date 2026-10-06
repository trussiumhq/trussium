"""Tests for fixed, application-composed remote MCP tool registrations."""

import json
import logging
from typing import Any

import httpx
import pytest
from pydantic import BaseModel, ConfigDict

from trussium.runtime import reset_request_id, set_request_id
from trussium.tools import (
    RemoteMCPTool,
    RemoteMCPToolError,
    ToolExecutor,
    ToolInvocation,
    ToolRegistry,
)


class SearchArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    query: str


def _tool(
    transport: httpx.AsyncBaseTransport,
    *,
    endpoint_url: str = "https://knowledge.example/v1/mcp",
) -> RemoteMCPTool:
    return RemoteMCPTool(
        name="knowledge.search",
        endpoint_url=endpoint_url,
        remote_name="docs.search",
        arguments_model=SearchArguments,
        bearer_token="secret-token",
        transport=transport,
    )


@pytest.mark.anyio
async def test_remote_mcp_tool_uses_only_its_registered_identity_and_context() -> None:
    observed: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        observed["headers"] = request.headers
        observed["body"] = json.loads(await request.aread())
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": observed["body"]["id"],
                "result": {
                    "isError": False,
                    "content": [{"type": "json", "json": {"matches": 2}}],
                },
            },
        )

    token = set_request_id("audit-request-123", execution_id="e93d9c1a-4c61-4a24-9ac4-587fbf50102f")
    try:
        executor = ToolExecutor(
            ToolRegistry((_tool(httpx.MockTransport(handler)).registered_tool(),))
        )
        result = await executor.execute(
            ToolInvocation(name="knowledge.search", arguments={"query": "runtime"})
        )
    finally:
        reset_request_id(token)

    assert result.output == {"matches": 2}
    assert observed["headers"]["authorization"] == "Bearer secret-token"
    assert observed["headers"]["x-request-id"] == "audit-request-123"
    assert observed["headers"]["x-execution-id"] == "e93d9c1a-4c61-4a24-9ac4-587fbf50102f"
    assert observed["body"]["method"] == "tools/call"
    assert observed["body"]["params"]["name"] == "docs.search"
    assert observed["body"]["params"]["arguments"] == {"query": "runtime"}
    assert "secret-token" not in repr(_tool(httpx.MockTransport(handler)))


@pytest.mark.anyio
async def test_remote_mcp_tool_does_not_follow_redirects() -> None:
    calls = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(307, headers={"Location": "https://attacker.example/v1/mcp"})

    registered = _tool(httpx.MockTransport(handler)).registered_tool()
    executor = ToolExecutor(ToolRegistry((registered,)))

    with pytest.raises(RemoteMCPToolError, match="Remote MCP request failed"):
        await executor.execute(ToolInvocation(name="knowledge.search", arguments={"query": "x"}))

    assert calls == 1


@pytest.mark.anyio
async def test_remote_mcp_tool_rejects_mismatched_response_id() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": "another-execution",
                "result": {"isError": False, "content": [{"type": "json", "json": {}}]},
            },
        )

    executor = ToolExecutor(ToolRegistry((_tool(httpx.MockTransport(handler)).registered_tool(),)))

    with pytest.raises(RemoteMCPToolError, match="correlation"):
        await executor.execute(ToolInvocation(name="knowledge.search", arguments={"query": "x"}))


@pytest.mark.anyio
async def test_remote_mcp_tool_rejects_remote_error_without_leaking_detail(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(await request.aread())
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": payload["id"],
                "error": {"code": -32000, "message": "private remote stack trace"},
            },
        )

    executor = ToolExecutor(ToolRegistry((_tool(httpx.MockTransport(handler)).registered_tool(),)))
    with (
        caplog.at_level(logging.WARNING, logger="trussium.tools.execution"),
        pytest.raises(RemoteMCPToolError, match="execution failed"),
    ):
        await executor.execute(
            ToolInvocation(name="knowledge.search", arguments={"query": "private query"})
        )

    assert "private remote stack trace" not in caplog.text
    assert "private query" not in caplog.text
    assert "secret-token" not in caplog.text


def test_remote_mcp_tool_requires_a_fixed_safe_endpoint() -> None:
    for endpoint in (
        "http://knowledge.example/v1/mcp",
        "https://user:pass@knowledge.example/v1/mcp",
        "https://knowledge.example/v1/mcp?next=https://attacker.example",
        "https://knowledge.example/other",
    ):
        with pytest.raises(ValueError):
            _tool(httpx.MockTransport(lambda _: httpx.Response(200)), endpoint_url=endpoint)


def test_remote_mcp_tool_allows_explicit_loopback_http_only() -> None:
    tool = RemoteMCPTool(
        name="knowledge.search",
        endpoint_url="http://127.0.0.1:8000/v1/mcp",
        remote_name="docs.search",
        arguments_model=SearchArguments,
        bearer_token="secret-token",
        allow_local_http=True,
    )

    assert tool.endpoint_url == "http://127.0.0.1:8000/v1/mcp"

    with pytest.raises(ValueError, match="loopback"):
        RemoteMCPTool(
            name="knowledge.search",
            endpoint_url="http://knowledge-agent:8000/v1/mcp",
            remote_name="docs.search",
            arguments_model=SearchArguments,
            bearer_token="secret-token",
            allow_local_http=True,
        )
