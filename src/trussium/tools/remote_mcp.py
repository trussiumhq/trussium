"""Explicit application-composed MCP tools for trusted remote applications."""

from __future__ import annotations

import json
import math
from contextlib import suppress
from dataclasses import dataclass, field
from ipaddress import ip_address
from typing import Any, cast
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from pydantic import BaseModel

from trussium.runtime import get_execution_context
from trussium.tools.contracts import RegisteredTool

_MAX_REQUEST_BYTES = 1_048_576
_MAX_RESPONSE_BYTES = 1_048_576
_EXECUTION_ID_HEADER = "X-Execution-ID"
_REQUEST_ID_HEADER = "X-Request-ID"


class RemoteMCPToolError(RuntimeError):
    """A remote MCP call failed without exposing transport or server details."""


@dataclass(frozen=True, slots=True)
class RemoteMCPTool:
    """A fixed remote MCP tool declaration for application composition.

    The endpoint, remote tool name, schema, and credential are fixed before
    requests are accepted. They are never read from invocation arguments.
    """

    name: str
    endpoint_url: str
    remote_name: str
    arguments_model: type[BaseModel]
    bearer_token: str = field(repr=False)
    timeout_seconds: float = 10.0
    allow_local_http: bool = False
    description: str = ""
    version: str = "1.0.0"
    transport: httpx.AsyncBaseTransport | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.remote_name.strip():
            raise ValueError("Remote MCP tool names must not be blank.")
        if not self.bearer_token.strip() or any(
            ord(char) < 33 or ord(char) > 126 for char in self.bearer_token
        ):
            raise ValueError("Remote MCP tools require a valid bearer token.")
        if not math.isfinite(self.timeout_seconds) or not 0 < self.timeout_seconds <= 120:
            raise ValueError("Remote MCP timeout must be greater than 0 and at most 120 seconds.")
        _validate_endpoint(self.endpoint_url, allow_local_http=self.allow_local_http)

    def registered_tool(self) -> RegisteredTool:
        """Return a local tool registration backed by this fixed remote tool."""

        async def invoke(arguments: BaseModel) -> dict[str, Any]:
            return await self._invoke(arguments)

        return RegisteredTool(
            name=self.name,
            arguments_model=self.arguments_model,
            handler=invoke,
            version=self.version,
            description=self.description,
        )

    async def _invoke(self, arguments: BaseModel) -> dict[str, Any]:
        context = get_execution_context()
        request_id = context.request_id
        execution_id = context.execution_id or str(uuid4())
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
            _EXECUTION_ID_HEADER: execution_id,
        }
        if (
            request_id is not None
            and len(request_id) <= 128
            and all(character.isalnum() or character in "-_.:" for character in request_id)
        ):
            headers[_REQUEST_ID_HEADER] = request_id

        request_body = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": execution_id,
                "method": "tools/call",
                "params": {
                    "name": self.remote_name,
                    "arguments": arguments.model_dump(mode="json"),
                },
            },
            separators=(",", ":"),
        ).encode()
        if len(request_body) > _MAX_REQUEST_BYTES:
            raise RemoteMCPToolError("Remote MCP request exceeds the configured size limit.")

        try:
            async with (
                httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout_seconds),
                    follow_redirects=False,
                    trust_env=False,
                    transport=self.transport,
                ) as client,
                client.stream(
                    "POST", self.endpoint_url, headers=headers, content=request_body
                ) as response,
            ):
                response.raise_for_status()
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > _MAX_RESPONSE_BYTES:
                        raise RemoteMCPToolError(
                            "Remote MCP response exceeds the configured size limit."
                        )
                    chunks.append(chunk)
        except RemoteMCPToolError:
            raise
        except httpx.HTTPError as error:
            raise RemoteMCPToolError("Remote MCP request failed.") from error

        try:
            payload = json.loads(b"".join(chunks))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RemoteMCPToolError("Remote MCP returned an invalid response.") from error
        return _validate_response(payload, execution_id)


def _validate_endpoint(endpoint_url: str, *, allow_local_http: bool) -> None:
    try:
        parsed = urlsplit(endpoint_url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as error:
        raise ValueError("Remote MCP endpoint URL is invalid.") from error

    if (
        parsed.scheme not in {"https", "http"}
        or hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path != "/v1/mcp"
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Remote MCP endpoint must be a credential-free /v1/mcp URL.")

    if parsed.scheme == "http":
        local_host = hostname.lower() == "localhost"
        with suppress(ValueError):
            local_host = local_host or ip_address(hostname).is_loopback
        if not allow_local_http or not local_host:
            raise ValueError("Plain HTTP is allowed only for explicitly enabled loopback hosts.")

    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Remote MCP endpoint port is invalid.")


def _validate_response(payload: object, request_id: str) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0":
        raise RemoteMCPToolError("Remote MCP returned an invalid response.")
    if payload.get("id") != request_id:
        raise RemoteMCPToolError("Remote MCP response correlation did not match the request.")
    if "error" in payload:
        raise RemoteMCPToolError("Remote MCP tool execution failed.")
    result = payload.get("result")
    if not isinstance(result, dict) or result.get("isError") is not False:
        raise RemoteMCPToolError("Remote MCP tool execution failed.")
    content = result.get("content")
    if (
        not isinstance(content, list)
        or len(content) != 1
        or not isinstance(content[0], dict)
        or content[0].get("type") != "json"
        or not isinstance(content[0].get("json"), dict)
    ):
        raise RemoteMCPToolError("Remote MCP returned an invalid tool result.")
    return cast(dict[str, Any], content[0]["json"])
