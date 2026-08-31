"""Tests for the controlled tool-execution endpoint."""

from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict

from trussium.app import create_application
from trussium.tools import RegisteredTool, ToolExecutor, ToolRegistry


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
