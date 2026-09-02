"""Tests for the controlled tool-execution endpoint."""

from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict

from trussium.app import create_application
from trussium.tools import RegisteredTool, ToolExecutor, ToolInvocation, ToolRegistry
from trussium.workflows import WorkflowAdmissionPolicy, WorkflowRequest, WorkflowStep


class EchoArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value: str


async def _echo(arguments: BaseModel) -> dict[str, object]:
    return {"value": arguments.model_dump()["value"]}


def test_tools_are_unavailable_without_application_registration() -> None:
    response = TestClient(create_application()).post(
        "/v1/tools/executions", json={"name": "echo", "arguments": {"value": "ok"}}
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "tools_unavailable"


def test_mcp_is_disabled_by_default() -> None:
    response = TestClient(create_application()).post(
        "/v1/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"}
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "mcp_unavailable"


def test_mcp_ping_returns_empty_result_when_enabled() -> None:
    client = TestClient(
        create_application(tool_executor=ToolExecutor(ToolRegistry()), mcp_enabled=True)
    )

    response = client.post("/v1/mcp", json={"jsonrpc": "2.0", "id": "ping-1", "method": "ping"})

    assert response.json() == {"jsonrpc": "2.0", "id": "ping-1", "result": {}}


def test_mcp_lists_and_executes_registered_tools() -> None:
    executor = ToolExecutor(ToolRegistry((RegisteredTool("echo", EchoArguments, _echo),)))
    client = TestClient(create_application(tool_executor=executor, mcp_enabled=True))

    listed = client.post("/v1/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    called = client.post(
        "/v1/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "echo", "arguments": {"value": "ok"}},
        },
    )

    assert listed.json()["result"]["tools"][0]["name"] == "echo"
    assert listed.json()["result"]["tools"][0]["inputSchema"]["properties"] == {
        "value": {"title": "Value", "type": "string"}
    }
    assert listed.json()["result"]["tools"][0]["inputSchema"]["required"] == ["value"]
    assert called.json()["result"]["content"] == [{"type": "json", "json": {"value": "ok"}}]


def test_mcp_returns_stable_errors_for_unknown_methods_and_tools() -> None:
    executor = ToolExecutor(ToolRegistry())
    client = TestClient(create_application(tool_executor=executor, mcp_enabled=True))

    method = client.post("/v1/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "resources/list"})
    tool = client.post(
        "/v1/mcp",
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "shell"}},
    )

    assert method.json()["error"] == {"code": -32601, "message": "Method not supported."}
    assert tool.json()["error"] == {"code": -32004, "message": "Tool not found."}


def test_mcp_tools_list_rejects_invalid_cursor() -> None:
    executor = ToolExecutor(ToolRegistry((RegisteredTool("echo", EchoArguments, _echo),)))
    client = TestClient(create_application(tool_executor=executor, mcp_enabled=True))

    response = client.post(
        "/v1/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {"cursor": "bad"}},
    )

    assert response.json()["error"] == {"code": -32602, "message": "Invalid tools/list cursor."}


def test_registered_tools_expose_only_safe_ordered_metadata() -> None:
    executor = ToolExecutor(
        ToolRegistry(
            (
                RegisteredTool(
                    "echo", EchoArguments, _echo, version="1.2.0", description="Echo a value."
                ),
            )
        )
    )
    response = TestClient(create_application(tool_executor=executor)).get("/v1/tools")

    assert response.status_code == 200
    assert response.json() == [{"name": "echo", "version": "1.2.0", "description": "Echo a value."}]


def test_declared_tool_validates_and_executes() -> None:
    executor = ToolExecutor(ToolRegistry((RegisteredTool("echo", EchoArguments, _echo),)))
    client = TestClient(create_application(tool_executor=executor))

    success = client.post(
        "/v1/tools/executions", json={"name": "echo", "arguments": {"value": "ok"}}
    )
    invalid = client.post("/v1/tools/executions", json={"name": "echo", "arguments": {"value": 1}})

    assert success.json() == {"tool_name": "echo", "output": {"value": "ok"}}
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "invalid_tool_arguments"


def test_unknown_tool_is_not_executable() -> None:
    client = TestClient(create_application(tool_executor=ToolExecutor(ToolRegistry())))

    response = client.post("/v1/tools/executions", json={"name": "shell", "arguments": {}})

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "tool_not_found"


def test_workflow_endpoint_executes_bounded_steps() -> None:
    executor = ToolExecutor(ToolRegistry((RegisteredTool("echo", EchoArguments, _echo),)))
    client = TestClient(create_application(tool_executor=executor))

    request = WorkflowRequest(
        steps=(
            WorkflowStep(
                id="first",
                invocation=ToolInvocation(name="echo", arguments={"value": "ok"}),
            ),
        )
    )
    response = client.post("/v1/workflows/executions", json=request.model_dump(mode="json"))

    assert response.status_code == 200
    assert response.json() == {
        "status": "completed",
        "steps": [{"tool_name": "echo", "output": {"value": "ok"}}],
    }


def test_workflow_endpoint_requires_configured_tools() -> None:
    response = TestClient(create_application()).post(
        "/v1/workflows/executions",
        json={"steps": [{"id": "first", "invocation": {"name": "echo", "arguments": {}}}]},
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "workflows_unavailable"


def test_workflow_endpoint_returns_stable_admission_rejection() -> None:
    executor = ToolExecutor(ToolRegistry((RegisteredTool("echo", EchoArguments, _echo),)))
    client = TestClient(
        create_application(
            tool_executor=executor,
            workflow_admission_policy=WorkflowAdmissionPolicy(max_depth=1),
        )
    )
    response = client.post(
        "/v1/workflows/executions",
        json={
            "steps": [{"id": "one", "invocation": {"name": "echo", "arguments": {}}}],
            "depth": 2,
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "workflow_depth_exceeded"
